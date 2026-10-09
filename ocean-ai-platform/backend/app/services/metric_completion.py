"""Measured raw diagnostics and printed references, never operational QC approval."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from functools import lru_cache
import calendar
import re
import pyarrow.parquet as pq

from fastapi import HTTPException

from app.core.config import settings
from app.services import lake_browser
from app.services.native_month_metrics import asset_month,typed_key,file_hash,digest,month_bounds,grid as replay_grid


BLOCKED = [
    {'key':'collection_rate','label':'실제 수집률','status':'INPUTS_MISSING',
     'reason':'승인된 관측 주기·센서 운영기간·시간대·예정 수집건수가 없습니다. 시간격자 보유율은 별도 진단입니다.',
     'required_inputs':['SAMPLING_CONTRACT','SENSOR_EFFECTIVE_PERIOD','TIMEZONE','EXPECTED_OBSERVATIONS']},
    {'key':'qc_normal_rate','label':'승인 QC 정상 비율','status':'INPUTS_MISSING',
     'reason':'원천 QC 판본·시행기간·코드 의미와 승인된 QC 집계가 없습니다. 보고서 정상자료율은 원문 참조입니다.',
     'required_inputs':['QC_CODEBOOK_EFFECTIVE_PERIOD','APPROVED_QC_COUNTS']},
    {'key':'qc_bad_rate','label':'승인 BAD 비율','status':'INPUTS_MISSING',
     'reason':'원천 QC 코드를 BAD로 바꾸는 승인 판정과 분류별 집계가 없습니다. 결측표현율을 BAD 비율로 바꾸지 않습니다.',
     'required_inputs':['QC_CODEBOOK_EFFECTIVE_PERIOD','APPROVED_BAD_COUNTS']},
    {'key':'reception_status','label':'정상·지연·중단 수신 상태','status':'INPUTS_MISSING',
     'reason':'수신시각이 있는 원천은 원문 시계차를 계산합니다. 정상·지연·중단 판정에는 확정된 관측/수신 시계·예정 수신격자·운영기간·허용 지연기준이 추가로 필요합니다.',
     'required_inputs':['OBSERVATION_CLOCK_CONTRACT','RECEIPT_CLOCK_CONTRACT','EXPECTED_RECEIPT_GRID','SENSOR_EFFECTIVE_PERIOD','ACCEPTABLE_RECEPTION_DELAY_THRESHOLD']},
]


def percent(numerator, denominator):
    return round(100*numerator/denominator,3) if numerator is not None and denominator else None


def grid_metrics(rows):
    eligible = [r for r in rows if r.get('grid',{}).get('expected_slots') is not None]
    expected = sum(r['grid']['expected_slots'] for r in eligible)
    held = sum(r['grid']['held_slots'] for r in eligible)
    excluded = Counter(r.get('grid',{}).get('status','NO_INTERVAL_EVIDENCE') for r in rows if r.get('grid',{}).get('expected_slots') is None)
    return {'status':'DIAGNOSTIC_AVAILABLE' if expected else 'NO_ELIGIBLE_GRID',
            'holding_fraction_percent':percent(held,expected),'held_slots':held,'expected_slots':expected,
            'eligible_channel_months':len(eligible),'excluded_channel_months':len(rows)-len(eligible),
            'excluded_reasons':dict(excluded),'approved_sampling_contract':False,
            'eligible_months':sorted({r.get('month') for r in eligible if r.get('month')}),
            'scope_is_full_selection':len(eligible)==len(rows),
            'reason':'실제 시각의 유일 최빈 간격·일정 위상으로 만든 전체 월 참고 격자입니다. 보유기간만으로 분모를 줄이지 않으며 간격·위상 미확정 채널은 제외합니다.'}


def raw_metrics(rows):
    total = sum(r['raw_rows'] for r in rows)
    def known_sum(key):
        active=[r for r in rows if r['raw_rows']]
        return sum(r[key] for r in active) if rows and all(r.get(key) is not None for r in active) else None
    missing = known_sum('missing_value_rows')
    numeric = known_sum('numeric_rows')
    invalid = known_sum('invalid_time_rows')
    qc = known_sum('source_qc_present_rows')
    counts = Counter()
    field_totals = Counter()
    for row in rows:
        for entry in row.get('qc_codes',[]):
            field,literal,count=entry['field'],entry['literal'],entry['count']
            counts[(field,literal)]+=count
            field_totals[field]+=count
    result={'held_rows':total,'missing_value_rows':missing,'missing_value_rate':percent(missing,total),
            'numeric_rows':numeric,'numeric_row_rate':percent(numeric,total),
            'invalid_time_rows':invalid,'invalid_time_rate':percent(invalid,total),
            'source_qc_present_rows':qc,'source_qc_presence_rate':percent(qc,total),
            'source_qc_primary_fields':sorted({r['source_qc_primary_field'] for r in rows if r.get('source_qc_primary_field')}),
            'source_qc_field_state':'NO_ROWS' if not total else 'ABSENT' if all(r.get('source_qc_field_state')=='ABSENT' for r in rows if r['raw_rows']) else 'PRESENT' if all(r.get('source_qc_field_state')=='PRESENT' for r in rows if r['raw_rows']) else 'PARTIAL_OR_UNKNOWN',
            'qc_code_distribution_coverage':{'calculated_held_rows':sum(r['raw_rows'] for r in rows if r.get('calculation_state')=='FULL_NATIVE_PARQUET_DIAGNOSTICS'),
              'selected_held_rows':total,'uninterpreted':True},
            'duplicate_timestamp_rows':known_sum('duplicate_timestamp_rows'),
            'unique_valid_month_timestamps':known_sum('unique_valid_month_timestamps'),
            'qc_codes':[{'field':field,'literal':literal,'count':count,
                         'percent_of_field_rows':percent(count,field_totals[field])}
                        for (field,literal),count in sorted(counts.items(),key=lambda p:(p[0][0],str(p[0][1])))],
            'grid':grid_metrics(rows)}
    stations={}
    for row in rows:stations.setdefault(row['station_code'],[]).append(row)
    result['stations']=[{'station_code':code,**raw_metrics_basic(group)}
                        for code,group in sorted(stations.items()) if any(r['raw_rows'] for r in group)]
    result['catalog_only_station_codes']=[code for code,group in sorted(stations.items()) if not any(r['raw_rows'] for r in group)]
    return result


def raw_metrics_basic(rows):
    total=sum(r['raw_rows'] for r in rows)
    def known_sum(key):
        active=[r for r in rows if r['raw_rows']]
        return sum(r[key] for r in active) if rows and all(r.get(key) is not None for r in active) else None
    return {'held_rows':total,'missing_value_rows':known_sum('missing_value_rows'),'missing_value_rate':percent(known_sum('missing_value_rows'),total),
            'numeric_rows':known_sum('numeric_rows'),'numeric_row_rate':percent(known_sum('numeric_rows'),total),
            'invalid_time_rows':known_sum('invalid_time_rows'),'invalid_time_rate':percent(known_sum('invalid_time_rows'),total),
            'source_qc_present_rows':known_sum('source_qc_present_rows'),'source_qc_presence_rate':percent(known_sum('source_qc_present_rows'),total),
            'first_native_clock':min((r.get('first_native_clock') for r in rows if r.get('first_native_clock')),default=None),
            'last_native_clock':max((r.get('last_native_clock') for r in rows if r.get('last_native_clock')),default=None),
            'selected_held_months':len({r.get('month') for r in rows if r['raw_rows'] and r.get('month')}),'grid':grid_metrics(rows)}


def report_metrics(rows):
    references={}
    for row in rows:
        for ref in row.get('report_refs',[]):
            identity=ref['rate_reference_id']
            if identity in references and references[identity]!=ref:
                raise HTTPException(409,'보고서 참고율의 동일 식별자 내용이 충돌합니다.')
            references[identity]=ref
    rates=list(references.values())
    numbers=[r['value'] for r in rates if r.get('value') is not None]
    return {'status':'REPORTED_REFERENCE_AVAILABLE' if numbers else 'NO_NUMERIC_REFERENCE',
            'normal_rates':rates,'unweighted_reference_mean_percent':round(sum(numbers)/len(numbers),3) if numbers else None,
            'numeric_reference_values':len(numbers),'excluded_reference_values':len(rates)-len(numbers),
            'reference_mean_method':'EACH_UNIQUE_PRINTED_STATION_ITEM_CELL_ONCE_UNWEIGHTED',
            'reason':'공식 표의 고유 시설·항목 수치 셀을 한 번씩 산술평균한 참조값입니다. 원문의 전체 평균·원시 정상 관측 행 비율을 재현한 값이 아닙니다.'}


def validate_packet(packet):
    """Fail closed on impossible counts, duplicate grains, or invented rates."""
    if packet['schema_version'] != 'metric-completion-1' or packet.get('approved') is not False:
        raise ValueError('invalid diagnostic contract')
    seen = set()
    for row in packet['channels']:
        grain = (row.get('source_group'),row.get('month',packet.get('report_month')),typed_key(row))
        if grain in seen: raise ValueError('duplicate grain')
        seen.add(grain)
        total = row['raw_rows']
        if type(total) is not int or total < 0: raise ValueError('invalid total')
        for key in ('missing_value_rows','numeric_rows','invalid_time_rows','source_qc_present_rows','duplicate_timestamp_rows','unique_valid_month_timestamps'):
            value = row[key]
            if value is not None and (type(value) is not int or value < 0 or value > total):
                raise ValueError('invalid count')
        grid = row['grid']
        if grid['expected_slots'] is not None:
            expected, held = grid['expected_slots'], grid['held_slots']
            if type(expected) is not int or expected <= 0 or type(held) is not int or not 0 <= held <= expected or held > total:
                raise ValueError('invalid grid')
        elif grid['held_slots'] is not None: raise ValueError('grid without denominator')
        for ref in row['report_refs']:
            value = ref['value']
            if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError('invalid printed rate')


def strict_json(raw):
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result:raise ValueError('DUPLICATE_JSON_KEY')
            result[key]=value
        return result
    def nonfinite(value):raise ValueError('NONFINITE_JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=nonfinite)


@lru_cache(maxsize=8)
def cached_catalog(path,mtime,size,sha):
    rows=pq.read_table(path).to_pylist()
    if file_hash(path)!=sha:raise HTTPException(409,'카탈로그가 조회 중 변경됐습니다.')
    return rows


def calendar_months(start,end):
    month_bounds(start);month_bounds(end)
    if start>end:raise ValueError('INVALID_MONTH_RANGE')
    result=[];year,mon=map(int,start.split('-'))
    while f'{year:04d}-{mon:02d}'<=end:
        result.append(f'{year:04d}-{mon:02d}')
        if len(result)>1200:raise ValueError('MONTH_RANGE_TOO_LARGE')
        year,mon=(year+1,1) if mon==12 else (year,mon+1)
    return result


def catalog_counts(view,source):
    if source=='HISTORICAL_RECONCILED':
        _,rows=lake_browser.history()
        path=lake_browser.historical_root()/'metadata/raw/manifest.json'
        return rows,{'path':str(path),'sha256':file_hash(path) if path.is_file() else None,
                     'basis':'HISTORICAL_MANIFEST_FOOTER_COUNTS_ONLY'}
    path=view/'station-item-month-validation.parquet';stat=path.stat();sha=file_hash(path)
    rows=cached_catalog(str(path),stat.st_mtime_ns,stat.st_size,sha)
    selected=[r for r in rows if r['source_group']==source]
    seen=set()
    for row in selected:
        key=(str(row['month'])[:7],typed_key(row))
        if key in seen:raise ValueError('DUPLICATE_CATALOG_CHANNEL_MONTH')
        seen.add(key)
    return selected,{'path':str(path),'sha256':sha,'basis':'IMMUTABLE_VALIDATION_CATALOG_EXACT_COUNTS'}


def catalog_channel(row,source):
    result={key:row.get(key) for key in ('station_code','item_code','depth_step','depth_from','depth_to')}
    result.update(source_group=source,month=str(row['month'])[:7],raw_rows=row['held_rows'] or 0,
      **{key:row.get(key) for key in ('numeric_rows','missing_value_rows','invalid_time_rows','source_qc_present_rows')},
      first_native_clock=str(row['first_clock']) if row.get('first_clock') is not None else None,
      last_native_clock=str(row['last_clock']) if row.get('last_clock') is not None else None,
      source_qc_primary_field='qc_raw' if source=='GD_OBS_ST_MONTHLY' else 'QC_FLAG' if source in ('GD_OBS_BU','GD_OBS_VBU') else None,
      source_qc_field_state='ABSENT' if source=='GR_OBS_ST' else 'PRESENT' if row.get('source_qc_present_rows') is not None else 'UNKNOWN_UNCALCULATED',
      unique_valid_month_timestamps=row.get('distinct_timestamps'),duplicate_timestamp_rows=None,
      qc_codes=[],report_refs=[],calculation_state='CATALOG_EXACT_COUNTS_ONLY',
      grid={'status':'MONTH_NATIVE_GRID_NOT_YET_CALCULATED','expected_slots':None,'held_slots':None})
    if source=='GR_OBS_ST':
        # Old coverage counts used 0 for absent QC columns. Absence has no percentage denominator.
        result['source_qc_present_rows']=None
    return result


def july_packet(view):
    directory=Path(settings.MONTHLY_REPORT_MATCHING_ROOT)/'202607'/'metric-enrichment'
    pointer=directory/'published.json'
    if not pointer.is_file():return None,None
    marker=strict_json(pointer.read_bytes());raw=(directory/'metric-completion.json').read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=marker['sha256']:raise HTTPException(409,'보완 지표 checksum 불일치')
    packet=strict_json(raw)
    if packet['report_month']!='2026-07' or marker['report_month']!='2026-07':raise HTTPException(409,'보완 지표 기준월 불일치')
    validate_packet(packet)
    if packet['snapshot']!=view.name:return None,'STALE'
    return packet,sha


def native_packet(view,source,month,catalog_rows,catalog_sha):
    directory=Path(settings.MONTHLY_REPORT_MATCHING_ROOT)/'native-metrics'/view.name/source/month
    pointer=directory/'published.json'
    if not pointer.is_file():return None,None
    marker=strict_json(pointer.read_bytes())
    name=marker['packet_file']
    if not isinstance(name,str) or not re.fullmatch(r'packet-[0-9a-f]{64}\.json',name):raise ValueError('PACKET_PATH_INVALID')
    for body in (marker,):
        if body['snapshot']!=view.name or body['source_group']!=source or body['month']!=month or body['approved'] is not False:
            raise ValueError('PACKET_PUBLICATION_SCOPE_MISMATCH')
    path=directory/name;raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=marker['sha256'] or name!='packet-'+sha+'.json':raise HTTPException(409,'월별 지표 checksum 불일치')
    packet=strict_json(raw)
    if packet['schema_version']!='native-month-metric-packet-1' or packet['snapshot']!=view.name or packet['source_group']!=source or packet['month']!=month:
        raise ValueError('PACKET_SCOPE_MISMATCH')
    if packet['approved'] is not False or packet['production_eligible'] is not False:raise ValueError('DIAGNOSTIC_MUST_BE_UNAPPROVED')
    if packet['catalog_sha256']!=catalog_sha:raise HTTPException(409,'월별 지표의 원천 카탈로그가 현재 검증본과 다릅니다.')
    assets_path=view/'file-only-timeseries.duckdb'
    if packet['source_assets_sha256']!=file_hash(assets_path):raise HTTPException(409,'월별 지표의 파일 목록이 현재 검증본과 다릅니다.')
    assets=[a for a in lake_browser.monthly_assets(str(assets_path),assets_path.stat().st_mtime_ns)
      if a['source_group']==source and asset_month(a)==month]
    expected={str(Path(a['parquet_path']).resolve()):a for a in assets}
    actual={str(Path(a['path']).resolve()):a for a in packet['source_files']}
    if len(actual)!=len(packet['source_files']) or set(actual)!=set(expected):raise ValueError('SOURCE_FILE_MEMBERSHIP_MISMATCH')
    root=lake_browser.historical_root() if source=='GD_OBS_ST_MONTHLY' else Path(settings.SHARE_MONTHLY_LAKE_ROOT).resolve()
    source_columns=None
    for p,entry in actual.items():
        path=Path(p)
        if not path.is_relative_to(root.resolve()) or entry['source_group']!=source or entry['sha256']!=expected[p]['parquet_sha256']:
            raise ValueError('SOURCE_FILE_SCOPE_OR_SHA_MISMATCH')
        stat=path.stat()
        if stat.st_size!=entry['bytes'] or stat.st_mtime_ns!=entry['mtime_ns']:raise HTTPException(409,'월별 지표 계산 후 원천 파일이 변경됐습니다.')
        lake_browser.verify_file(p,stat.st_mtime_ns,stat.st_size,entry['sha256'])
        footer=pq.ParquetFile(path)
        if footer.metadata.num_rows!=entry['footer_rows']:raise ValueError('SOURCE_FOOTER_MISMATCH')
        schema=[{'column':f.name,'arrow_type':str(f.type)} for f in footer.schema_arrow]
        if schema!=entry['schema']:raise ValueError('SOURCE_SCHEMA_MISMATCH')
        current_columns=set(footer.schema_arrow.names)
        if source_columns is None:source_columns=current_columns
        elif source_columns!=current_columns:raise ValueError('SOURCE_SCHEMA_VARIANTS')
    expected_qc_fields={f for f in ('qc_raw','mq_raw','n1_aqc_raw') if f in source_columns} if source=='GD_OBS_ST_MONTHLY' else {f for f in source_columns if f.endswith('_FLAG')}
    expected_primary='qc_raw' if source=='GD_OBS_ST_MONTHLY' and 'qc_raw' in source_columns else 'QC_FLAG' if source!='GD_OBS_ST_MONTHLY' and 'QC_FLAG' in source_columns else None
    validate_packet({'schema_version':'metric-completion-1','approved':False,'report_month':month,'channels':packet['channels']})
    saved={typed_key(r):r for r in catalog_rows}
    if {typed_key(r) for r in packet['channels']}!=set(saved):raise ValueError('CHANNEL_MEMBERSHIP_MISMATCH')
    for row in packet['channels']:
        if row['source_group']!=source or row['month']!=month:raise ValueError('CHANNEL_SCOPE_MISMATCH')
        if row['channel_sha256']!=digest({k:v for k,v in row.items() if k!='channel_sha256'}):raise ValueError('CHANNEL_HASH_MISMATCH')
        original=saved[typed_key(row)]
        if row['raw_rows']!=(original['held_rows'] or 0):raise ValueError('CHANNEL_CATALOG_COUNT_MISMATCH')
        for field in ('numeric_rows','missing_value_rows','invalid_time_rows','source_qc_present_rows'):
            if field=='source_qc_present_rows' and expected_primary is None:continue
            if original.get(field) is not None and row[field]!=original[field]:raise ValueError('CHANNEL_CATALOG_VALUE_COUNT_MISMATCH')
        qc=row['qc_codes'];totals=Counter()
        for code in qc:
            if not isinstance(code['field'],str) or (code['literal'] is not None and not isinstance(code['literal'],str)) or type(code['count']) is not int or code['count']<0:
                raise ValueError('QC_LITERAL_OR_COUNT_INVALID')
            totals[code['field']]+=code['count']
        if any(count!=row['raw_rows'] for count in totals.values()):raise ValueError('QC_DISTRIBUTION_COUNT_MISMATCH')
        primary=row.get('source_qc_primary_field')
        if primary!=expected_primary:raise ValueError('QC_PRIMARY_NOT_IN_SOURCE_SCHEMA')
        if row['raw_rows'] and set(totals)!=expected_qc_fields:raise ValueError('QC_FIELDS_NOT_BOUND_TO_SOURCE_SCHEMA')
        if not row['raw_rows']:
            if row['source_qc_present_rows'] is not None or qc or row['source_qc_field_state']!='NO_ROWS':
                raise ValueError('EMPTY_CATALOG_QC_MUST_BE_UNKNOWN')
        elif primary:
            present=sum(c['count'] for c in qc if c['field']==primary and c['literal'] is not None and c['literal'].strip()!='')
            if totals[primary]!=row['raw_rows'] or present!=row['source_qc_present_rows']:raise ValueError('QC_PRIMARY_PRESENCE_MISMATCH')
        elif row['source_qc_present_rows'] is not None:raise ValueError('ABSENT_QC_PRESENCE_MUST_BE_NULL')
        if row['raw_rows']:
            for field in ('nonfinite_numeric_rows','nonnumeric_value_rows','outside_month_rows','valid_month_rows','unsupported_clock_representation_rows'):
                if type(row[field]) is not int or not 0<=row[field]<=row['raw_rows']:raise ValueError('NATIVE_ROW_PARTITION_INVALID')
            if sum(row[k] for k in ('numeric_rows','missing_value_rows','nonfinite_numeric_rows','nonnumeric_value_rows'))!=row['raw_rows']:
                raise ValueError('NATIVE_VALUE_PARTITION_MISMATCH')
            if sum(row[k] for k in ('invalid_time_rows','outside_month_rows','valid_month_rows','unsupported_clock_representation_rows'))!=row['raw_rows']:
                raise ValueError('NATIVE_CLOCK_PARTITION_MISMATCH')
            if row['unique_valid_month_timestamps']+row['duplicate_timestamp_rows']!=row['valid_month_rows']:
                raise ValueError('NATIVE_TIMESTAMP_DEDUPLICATION_MISMATCH')
            supplied=row['grid'];intervals=supplied['positive_interval_distribution'];phases=supplied['phase_distribution']
            for entry in intervals:
                if type(entry['microseconds']) is not int or entry['microseconds']<=0 or type(entry['count']) is not int or entry['count']<=0:
                    raise ValueError('NATIVE_INTERVAL_DISTRIBUTION_INVALID')
            if len({d['microseconds'] for d in intervals})!=len(intervals) or sum(d['count'] for d in intervals)!=max(row['unique_valid_month_timestamps']-1,0):
                raise ValueError('NATIVE_INTERVAL_ACCOUNTING_MISMATCH')
            for entry in phases:
                if any(type(entry[k]) is not int or entry[k]<0 for k in ('microseconds','unique_timestamp_count','raw_rows')) or entry['raw_rows']<entry['unique_timestamp_count']:
                    raise ValueError('NATIVE_PHASE_DISTRIBUTION_INVALID')
            if len({d['microseconds'] for d in phases})!=len(phases):raise ValueError('DUPLICATE_NATIVE_PHASE')
            maximum=max((r['count'] for r in intervals),default=0)
            modes=[r['microseconds'] for r in intervals if r['count']==maximum]
            if len(modes)==1:
                if sum(d['unique_timestamp_count'] for d in phases)!=row['unique_valid_month_timestamps'] or sum(d['raw_rows'] for d in phases)!=row['valid_month_rows']:
                    raise ValueError('NATIVE_PHASE_PARTITION_MISMATCH')
                if any(d['microseconds']>=modes[0] for d in phases):raise ValueError('NATIVE_PHASE_OUTSIDE_INTERVAL')
            elif phases:raise ValueError('PHASE_WITHOUT_UNIQUE_INTERVAL_MODE')
            repeated=replay_grid(month,intervals,phases,row['duplicate_timestamp_rows'])
            if row['unsupported_clock_representation_rows']:
                repeated.update(status='CLOCK_REPRESENTATION_UNVERIFIED',expected_slots=None,held_slots=None,holding_fraction_percent=None)
            if supplied!=repeated:raise ValueError('FULL_MONTH_GRID_REPLAY_MISMATCH')
    sums=packet['source_file_verification'];raw_rows=sum(r['raw_rows'] for r in packet['channels']);footer=sum(a['footer_rows'] for a in actual.values())
    if sums['files']!=len(actual) or sums['footer_rows']!=footer or sums['actual_observation_rows']!=raw_rows or sums['non_observation_rows']+raw_rows!=footer or sums['sha256_before_and_after_all_files'] is not True:
        raise ValueError('SOURCE_ROW_RECONCILIATION_MISMATCH')
    return packet,sha


def completion(source,start,end,station='',item='',station_scope=None):
    view,_=lake_browser.context()
    base={'snapshot':view.name,'source':source,'from_month':start,'to_month':end,
          'scope':{'station':station,'item':item,'station_scope_applied':station_scope is not None},
          'raw':None,'report_reference':None,'blocked_metrics':BLOCKED,
          'limitations':['시간격자·결측표현·QC 코드 분포는 원시 자료 진단입니다. 운영 승인이나 정상·고장 판정이 아닙니다.',
                         '시각·단위·센서 기간·QC 계약은 아직 미승인입니다. 원천을 자동 합산하지 않습니다.']}
    try:
        months=calendar_months(start,end)
        legacy,legacy_sha=july_packet(view) if '2026-07' in months else (None,None)
        catalog_available=(view/'station-item-month-validation.parquet').is_file() or source=='HISTORICAL_RECONCILED'
        if catalog_available:
            census,catalog_evidence=catalog_counts(view,source)
        elif legacy and start==end=='2026-07':
            # Isolated compatibility snapshots may only contain the previous July publication.
            census=[];catalog_evidence=None
        else:
            return {**base,'state':'STALE' if legacy_sha=='STALE' else 'UNAVAILABLE_PERIOD',
                    'reason':'현재 검증본의 선택 기간 카탈로그·진단 기록이 없습니다.'}
        monthly=[];rows=[];receipts=[];generated=[]
        for month in months:
            saved=[r for r in census if str(r['month'])[:7]==month]
            previous=[dict(r,month='2026-07',calculation_state='FULL_NATIVE_PARQUET_DIAGNOSTICS' if r['raw_rows'] else 'CATALOG_REFERENCE_ONLY')
              for r in legacy['channels'] if r['source_group']==source] if month=='2026-07' and legacy else []
            if previous and catalog_available:
                current={typed_key(r):r for r in saved if r.get('held_rows')}
                held={typed_key(r):r for r in previous if r['raw_rows']}
                if set(current)!=set(held):raise ValueError('JULY_LEGACY_CURRENT_CENSUS_MEMBERSHIP_MISMATCH')
                for key,old in held.items():
                    known=current[key]
                    if old['raw_rows']!=known['held_rows']:raise ValueError('JULY_LEGACY_CURRENT_CENSUS_COUNT_MISMATCH')
                    for field in ('missing_value_rows','numeric_rows','invalid_time_rows','source_qc_present_rows'):
                        if field=='source_qc_present_rows' and source=='GR_OBS_ST' and old['source_qc_field_state']=='ABSENT' and old.get('source_qc_primary_field') is None:continue
                        if known.get(field) is not None and old[field]!=known[field]:raise ValueError('JULY_LEGACY_CURRENT_CENSUS_VALUE_COUNT_MISMATCH')
                    old['first_native_clock']=str(known['first_clock']) if known.get('first_clock') is not None else None
                    old['last_native_clock']=str(known['last_clock']) if known.get('last_clock') is not None else None
            packet,sha=native_packet(view,source,month,saved,catalog_evidence['sha256']) if catalog_available and source!='HISTORICAL_RECONCILED' else (None,None)
            if packet:
                selected=[dict(r) for r in packet['channels']]
                # Report cell references require the same snapshot, exact source and typed grain, July only.
                prior={typed_key(r):r for r in previous}
                for row in selected:
                    row['report_refs']=prior.get(typed_key(row),{}).get('report_refs',[])
                present={typed_key(r) for r in selected}
                selected += [r for r in previous if not r['raw_rows'] and typed_key(r) not in present]
                evidence={'month':month,'sha256':sha,**packet['source_file_verification']}
                generated.append(packet['generated_at']);method='FULL_NATIVE_PARQUET_DIAGNOSTICS'
            elif previous:
                selected=previous;evidence={'month':month,'sha256':legacy_sha,**legacy['source_file_verification']}
                generated.append(legacy['generated_at']);method='FULL_NATIVE_PARQUET_DIAGNOSTICS'
            else:
                selected=[catalog_channel(r,source) for r in saved]
                evidence=None;method='CATALOG_EXACT_COUNTS_ONLY' if selected else 'NO_HELD_CATALOG_FOR_MONTH'
            selected=[r for r in selected if (not station or r['station_code']==station) and (not item or r['item_code']==item)]
            if station_scope is not None:
                if 'include' in station_scope:selected=[r for r in selected if r['station_code'] in station_scope['include']]
                else:selected=[r for r in selected if r['station_code'] not in station_scope['exclude']]
            rows+=selected
            monthly.append({'month':month,'state':method,'channel_months':len(selected),
              'held_rows':sum(r['raw_rows'] for r in selected),
              'grid_eligible_channel_months':sum(r.get('grid',{}).get('expected_slots') is not None for r in selected),
              'grid_excluded_channel_months':sum(r.get('grid',{}).get('expected_slots') is None for r in selected)})
            if evidence:receipts.append(evidence)
        # Every selected grain/month remains explicit; uncomputed statistics never become zero percentages.
        held_months=[m['month'] for m in monthly if m['held_rows']]
        computed_months=[m['month'] for m in monthly if m['held_rows'] and m['state']=='FULL_NATIVE_PARQUET_DIAGNOSTICS']
        pending=[m['month'] for m in monthly if m['held_rows'] and m['state']=='CATALOG_EXACT_COUNTS_ONLY']
        raw=raw_metrics(rows)
        reference=report_metrics(rows)
        reference.update(reference_months=['2026-07'] if any(r['report_refs'] for r in rows) else [],
          applies_to_full_selected_period=start==end=='2026-07')
        if start!=end or start!='2026-07':
            reference['reason']='보고서 참조는 2026년 7월의 동일 원문 셀에만 한정합니다. 다른 월의 정상자료율로 재사용하지 않습니다. '+reference['reason']
        from app.services.native_receipt_diagnostics import receipt_diagnostics
        receipt=receipt_diagnostics(source,start,end,station,item,station_scope,snapshot=view.name)
        receipt_metadata={k:v for k,v in receipt.items() if k not in ('raw','stations','channels')}
        raw['receipt_diagnostics']={**(receipt.get('raw') or {}),**receipt_metadata,
          'channel_months':len(receipt.get('channels',[]))}
        station_metadata={k:receipt_metadata[k] for k in ('diagnostic_kind','approved','operational_delay') if k in receipt_metadata}
        by_station={r['station_code']:{**r['receipt_diagnostics'],**station_metadata} for r in receipt.get('stations',[])}
        for row in raw['stations']:row['receipt_diagnostics']=by_station.get(row['station_code'])
        state='EMPTY_SCOPE' if not any(r['raw_rows'] for r in rows) else 'PARTIAL_CATALOG_COUNTS' if pending else 'AVAILABLE'
        coverage={'selected_calendar_months':len(months),'selected_held_months':len(held_months),
          'fully_scanned_held_months':len(computed_months),'fully_scanned_months':computed_months,
          'uncalculated_held_months':pending,'uncalculated_held_month_count':len(pending),
          'months_without_held_catalog':[m['month'] for m in monthly if not m['held_rows']],
          'selected_held_channel_months':sum(r['raw_rows']>0 for r in rows),
          'fully_scanned_held_channel_months':sum(r['raw_rows']>0 and r['calculation_state']=='FULL_NATIVE_PARQUET_DIAGNOSTICS' for r in rows),
          'grid_eligible_channel_months':raw['grid']['eligible_channel_months'],
          'grid_excluded_channel_months':raw['grid']['excluded_channel_months'],
          'grid_applies_to_full_selected_scope':raw['grid']['scope_is_full_selection'] and all(m['held_rows'] for m in monthly),
          'no_cross_source_deduplication':True,'no_held_period_denominator_shortening':True,
          'reason':'원천·월·관측소·항목·타입 보존 수심별 전체 월 분모입니다. 미계산·간격/위상 미확정 채널은 격자율에서 제외하며 선택 기간의 보유행 수에는 남깁니다.'}
        if catalog_evidence and catalog_evidence['sha256'] is not None and file_hash(catalog_evidence['path'])!=catalog_evidence['sha256']:
            raise HTTPException(409,'선택 기간 집계 중 카탈로그가 변경됐습니다.')
        return {**base,'state':state,'raw':raw,'report_reference':reference,'channel_months':len(rows),
          'audit_sha256':legacy_sha if start==end=='2026-07' and not any(p['sha256']!=legacy_sha for p in receipts) else digest(receipts),
          'generated_at':max(generated,default=None),'source_file_verification':{'monthly':receipts},
          'catalog_evidence':catalog_evidence,'monthly':monthly,'calculation_coverage':coverage,
          'reason':'선택 기간의 보유·수치·QC 표기 카탈로그 집계와 실제 계산한 월별 격자 진단을 함께 반환합니다.'}
    except HTTPException:raise
    except (OSError,KeyError,ValueError,TypeError,AttributeError):
        raise HTTPException(503,'보완 지표 기록을 읽을 수 없습니다.')
