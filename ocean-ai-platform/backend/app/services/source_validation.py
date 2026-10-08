"""원천 검증·근거 기반 시점 매핑·표준행 검사·설정형 QC. 원본을 변경하지 않는다."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from statistics import median
import hashlib, json, math

VERSION = 'source-validation-1'

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def utc(value):
    t=datetime.fromisoformat(value)
    if t.tzinfo is None or t.utcoffset() is None: raise ValueError('TIMEZONE_REQUIRED')
    return t.astimezone(timezone.utc)

def audit_raw(rows):
    """원천 단위/시각 그대로 검사. MAD는 탐색 후보이며 QC 정상/불량 판정이 아니다."""
    groups=defaultdict(list)
    for r in rows: groups[(str(r['station_id_raw']),r['item_code_raw'])].append(r)
    result=[]
    for key, group in sorted(groups.items()):
        seen={}; times=[]; values=[]; flags=Counter(); examples=[]; qc=Counter()
        for r in group:
            t=datetime.fromisoformat(r['observed_at_raw']); times.append(t)
            v=r.get('value_raw_numeric'); qc[json.dumps(r.get('source_qc_fields',{}),sort_keys=True)]+=1
            payload=(v,json.dumps(r.get('source_qc_fields',{}),sort_keys=True))
            if t in seen: flags['DUPLICATE_IDENTICAL' if seen[t]==payload else 'DUPLICATE_CONFLICT']+=1
            else: seen[t]=payload
            if v is None: flags['MISSING_VALUE']+=1; values.append(None)
            else:
                n=float(v)
                if not math.isfinite(n): flags['NONFINITE']+=1; values.append(None)
                else:
                    values.append(n)
                    if n==-999: flags['SENTINEL_CANDIDATE_MINUS_999']+=1
        flags['TIME_REVERSAL']=sum(b<a for a,b in zip(times,times[1:]))
        unique=sorted(set(times)); gaps=[(b-a).total_seconds() for a,b in zip(unique,unique[1:])]
        # 미확정 센티널을 정상값으로 사용하거나 결측으로 확정하지 않고 탐색에서 제외한다.
        finite=[v for v in values if v is not None and v!=-999]
        center=median(finite) if finite else None
        mad=median([abs(v-center) for v in finite]) if finite else None
        if mad:
            for r,v in zip(group,values):
                if v is not None and v!=-999 and abs(v-center)>6*1.4826*mad:
                    flags['DISTRIBUTION_REVIEW_CANDIDATE']+=1
                    if len(examples)<20: examples.append({'time_raw':r['observed_at_raw'],'value_raw':v})
        result.append({'station_raw':key[0],'item_raw':key[1],'records':len(group),'time_min_raw':min(times).isoformat(),'time_max_raw':max(times).isoformat(),'checks':dict(flags),'observed_gap_seconds_median':median(gaps) if gaps else None,'observed_gap_seconds_max':max(gaps) if gaps else None,'expected_cadence':None,'missing_timestamps':'NOT_EVALUATED_CADENCE_UNVERIFIED','source_qc_counts':dict(qc),'exploratory_median':center,'exploratory_MAD':mad,'outlier_examples_max20':examples,'outlier_method':'GLOBAL_MAD_6; REVIEW_ONLY; seasonal/sensor transitions not adjusted','status':'PRECHECK_ONLY_NOT_RELEASE_APPROVAL'})
    return {'version':VERSION,'records':len(rows),'series':result}

def verified(e):
    return isinstance(e,dict) and e.get('status')=='VERIFIED' and bool(e.get('references'))

def normalize(rows, contract, actual_hash):
    """검토된 원천 계약과 유효기간이 정확히 하나인 센서 매핑만 변환한다."""
    missing=[]
    if actual_hash!=contract.get('source_sha256'): missing.append('SOURCE_HASH_MISMATCH')
    for k in ['inventory','station','items','units','timezone','role','qc_policy','sensor_history','datum']:
        if not verified(contract.get('evidence',{}).get(k)): missing.append(k.upper()+'_UNVERIFIED')
    if contract.get('role')!='OBSERVED': missing.append('ROLE_NOT_OBSERVED')
    if missing: return [], {'status':'BLOCKED','reasons':missing,'input_records':len(rows),'output_records':0}
    if not isinstance(contract.get('source_utc_offset_minutes'),int): raise ValueError('OFFSET_REQUIRED')
    tz=timezone(timedelta(minutes=contract['source_utc_offset_minutes']))
    factors={('cm','m'):Decimal('.01'),('hPa','Pa'):Decimal('100'),('m/s','m/s'):Decimal(1)}
    output=[]; rejected=[]
    for ordinal,r in enumerate(rows):
        try:
            if str(r['station_id_raw'])!=str(contract['source_station_id']): raise ValueError('STATION_MISMATCH')
            item=contract['item_mapping'][r['item_code_raw']]
            rawtime=datetime.fromisoformat(r['observed_at_raw'])
            if rawtime.tzinfo is not None: raise ValueError('EXPECTED_SOURCE_NAIVE_CLOCK')
            t=rawtime.replace(tzinfo=tz).astimezone(timezone.utc)
            matches=[]
            for b in contract['bindings']:
                if b['station_id']!=contract['station_id'] or b['variable_code']!=item['variable_code']: continue
                if not verified(b.get('evidence')) or not b.get('valid_from') or not b.get('valid_to'): continue
                if utc(b['valid_from'])<=t<utc(b['valid_to']): matches.append(b)
            if len(matches)!=1: raise ValueError('SENSOR_BINDING_MISSING_OR_AMBIGUOUS')
            b=matches[0]
            if not b.get('sensor_id') or not b.get('equipment_code'): raise ValueError('PHYSICAL_SENSOR_OR_EQUIPMENT_MISSING')
            if r.get('value_raw_numeric') is None: raise ValueError('MISSING_VALUE')
            n=Decimal(r['value_raw_numeric'])
            if not n.is_finite(): raise ValueError('NONFINITE')
            if str(r['value_raw_numeric']) in contract.get('missing_markers',[]): raise ValueError('SOURCE_SENTINEL')
            # -999가 코드북에서 해소되지 않으면 물리값으로 공개하지 않는다.
            if n==Decimal('-999') and not contract.get('minus_999_is_valid_value',False): raise ValueError('UNRESOLVED_SENTINEL')
            factor=factors[(item['source_unit'],item['target_unit'])]
            output.append({'station_id':contract['station_id'],'sensor_id':b['sensor_id'],'equipment_code':b['equipment_code'],'variable_code':item['variable_code'],'timestamp_utc':t.isoformat(),'value':float(n*factor),'unit':item['target_unit'],'source_value':str(n),'source_time':r['observed_at_raw'],'source_item':r['item_code_raw'],'source_record_number':r.get('source_record_number',ordinal+1),'source_qc':r.get('source_qc_fields',{}),'source_qc_status':'PRESERVED_NOT_LABEL','source_sha256':actual_hash,'mapping_version':contract['version']})
        except (KeyError,ValueError,ArithmeticError) as e: rejected.append({'ordinal':ordinal,'reason':str(e)})
    # 일부 행만 조용히 공개하지 않는다. 전체 배치 검토/격리 후 재범위를 정한다.
    if rejected: return [], {'status':'BLOCKED_ROWS','input_records':len(rows),'candidate_records':len(output),'output_records':0,'rejected':rejected}
    post=validate_normalized(output)
    return (output if post['status']=='PASS' else []), {'status':post['status'],'input_records':len(rows),'output_records':len(output) if post['status']=='PASS' else 0,'post_validation':post}

def validate_normalized(rows):
    errors=[]; seen=set()
    if not rows: errors.append('EMPTY_BATCH')
    for i,r in enumerate(rows):
        try:
            for k in ['station_id','sensor_id','equipment_code','variable_code','unit','source_sha256','mapping_version']:
                if not r.get(k): raise ValueError('MISSING_'+k)
            if len(r['source_sha256'])!=64 or any(c not in '0123456789abcdef' for c in r['source_sha256']): raise ValueError('INVALID_SOURCE_SHA256')
            t=utc(r['timestamp_utc'])
            if datetime.fromisoformat(r['timestamp_utc']).utcoffset()!=timedelta(0): raise ValueError('NOT_CANONICAL_UTC')
            if not math.isfinite(r['value']): raise ValueError('NONFINITE')
            key=(r['station_id'],r['sensor_id'],r['variable_code'],t)
            if key in seen: raise ValueError('DUPLICATE_STANDARD_KEY')
            seen.add(key)
        except (ValueError,TypeError,KeyError) as e: errors.append({'ordinal':i,'reason':str(e)})
    return {'status':'FAIL' if errors else 'PASS','records':len(rows),'errors':errors}

def precise_qc(rows, rules):
    """명시적으로 승인된 시계열별 규칙만 실행. 결측/긴 공백/센서 교체를 가로질러 비교하지 않는다."""
    validation=validate_normalized(rows)
    if validation['status']!='PASS': return {'status':'NOT_EVALUATED_INVALID_STANDARD_INPUT','validation':validation,'results':[]}
    groups=defaultdict(list); results=[]
    for r in rows: groups[(r['station_id'],r['sensor_id'],r['variable_code'])].append(r)
    for key,group in groups.items():
        rule=rules.get('|'.join(key)); group.sort(key=lambda x:utc(x['timestamp_utc']))
        if not rule or not verified(rule.get('evidence')) or not rule.get('version'):
            results.append({'series':key,'status':'NOT_EVALUATED_RULE_UNVERIFIED'});continue
        numeric=['lower','upper','rate_per_second','max_gap_seconds','stuck_seconds']
        invalid=any(k in rule and (not isinstance(rule[k],(int,float)) or not math.isfinite(rule[k])) for k in numeric)
        invalid=invalid or any(k in rule and rule[k]<=0 for k in ['max_gap_seconds','stuck_seconds'])
        invalid=invalid or ('rate_per_second' in rule and rule['rate_per_second']<0)
        invalid=invalid or ('lower' in rule and 'upper' in rule and rule['lower']>rule['upper'])
        if invalid:
            results.append({'series':key,'status':'NOT_EVALUATED_INVALID_RULE_CONFIG'});continue
        if any(r['unit']!=rule.get('unit') for r in group):
            results.append({'series':key,'status':'NOT_EVALUATED_UNIT_MISMATCH'});continue
        if not rule.get('valid_from') or not rule.get('valid_to'):
            results.append({'series':key,'status':'NOT_EVALUATED_RULE_PERIOD_UNCONFIRMED'});continue
        previous=None; run_start=None
        for r in group:
            t=utc(r['timestamp_utc']); checks={}
            if not utc(rule['valid_from'])<=t<utc(rule['valid_to']):
                results.append({'series':key,'time':r['timestamp_utc'],'status':'NOT_EVALUATED_OUTSIDE_RULE_PERIOD'});previous=None;run_start=None;continue
            checks['range']='NOT_EVALUATED' if 'lower' not in rule or 'upper' not in rule else 'REVIEW' if not rule['lower']<=r['value']<=rule['upper'] else 'PASS'
            gap=(t-utc(previous['timestamp_utc'])).total_seconds() if previous else None
            contiguous=gap is not None and gap>0 and rule.get('max_gap_seconds') is not None and gap<=rule['max_gap_seconds']
            checks['rate']='NOT_EVALUATED' if not contiguous or 'rate_per_second' not in rule else 'REVIEW' if abs(r['value']-previous['value'])/gap>rule['rate_per_second'] else 'PASS'
            if not contiguous or previous['value']!=r['value']:run_start=t
            checks['stuck']='NOT_EVALUATED' if not contiguous or 'stuck_seconds' not in rule else 'REVIEW' if (t-run_start).total_seconds()>=rule['stuck_seconds'] else 'PASS'
            results.append({'series':key,'time':r['timestamp_utc'],'rule_version':rule['version'],'checks':checks,'label_status':'NOT_A_LABEL'});previous=r
    return {'status':'EXECUTED','version':VERSION,'results':results}
