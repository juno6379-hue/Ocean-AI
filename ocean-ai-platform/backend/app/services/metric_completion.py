"""Measured raw diagnostics and printed references, never operational QC approval."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings
from app.services import lake_browser


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
     'reason':'기간별 예정 수신 시각·수신 이력·센서 운영기간이 없습니다. 마지막 보유 시각은 실시간 상태가 아닙니다.',
     'required_inputs':['RECEIPT_CLOCK_CONTRACT','EXPECTED_RECEIPT_GRID','SENSOR_EFFECTIVE_PERIOD']},
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
            'reason':'실제 시각의 유일 최빈 간격·일정 위상으로 만든 전체 월 참고 격자입니다. 보유기간만으로 분모를 줄이지 않으며 간격·위상 미확정 채널은 제외합니다.'}


def raw_metrics(rows):
    total = sum(r['raw_rows'] for r in rows)
    def known_sum(key):
        return sum(r[key] for r in rows) if rows and all(r.get(key) is not None for r in rows) else None
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
            'source_qc_field_state':'ABSENT' if rows and all(r.get('source_qc_field_state')=='ABSENT' for r in rows) else 'PRESENT' if rows else 'NO_ROWS',
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
        return sum(r[key] for r in rows) if rows and all(r.get(key) is not None for r in rows) else None
    return {'held_rows':total,'missing_value_rate':percent(known_sum('missing_value_rows'),total),
            'source_qc_presence_rate':percent(known_sum('source_qc_present_rows'),total),'grid':grid_metrics(rows)}


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
        grain = tuple(row.get(k) for k in ('source_group','station_code','item_code','depth_step','depth_from','depth_to'))
        if grain in seen: raise ValueError('duplicate grain')
        seen.add(grain)
        total = row['raw_rows']
        if not isinstance(total,int) or total < 0: raise ValueError('invalid total')
        for key in ('missing_value_rows','numeric_rows','invalid_time_rows','source_qc_present_rows','duplicate_timestamp_rows','unique_valid_month_timestamps'):
            value = row[key]
            if value is not None and (not isinstance(value,int) or value < 0 or value > total):
                raise ValueError('invalid count')
        grid = row['grid']
        if grid['expected_slots'] is not None:
            expected, held = grid['expected_slots'], grid['held_slots']
            if not isinstance(expected,int) or expected <= 0 or not isinstance(held,int) or not 0 <= held <= expected or held > total:
                raise ValueError('invalid grid')
        elif grid['held_slots'] is not None: raise ValueError('grid without denominator')
        for ref in row['report_refs']:
            value = ref['value']
            if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError('invalid printed rate')


def completion(source,start,end,station='',item='',station_scope=None):
    view,_=lake_browser.context()
    base={'snapshot':view.name,'source':source,'from_month':start,'to_month':end,
          'scope':{'station':station,'item':item,'station_scope_applied':station_scope is not None},
          'raw':None,'report_reference':None,'blocked_metrics':BLOCKED,
          'limitations':['시간격자·결측표현·QC 코드 분포는 원시 자료 진단입니다. 운영 승인이나 정상·고장 판정이 아닙니다.',
                         '시각·단위·센서 기간·QC 계약은 아직 미승인입니다. 원천을 자동 합산하지 않습니다.']}
    if start!=end or start!='2026-07':
        return {**base,'state':'UNAVAILABLE_PERIOD','reason':'선택 기간의 전수 시간격자 분석이 없습니다. 2026년 7월 진단을 다른 기간에 적용하지 않습니다.'}
    directory=Path(settings.MONTHLY_REPORT_MATCHING_ROOT)/'202607'/'metric-enrichment'
    pointer=directory/'published.json'
    if not pointer.is_file():
        return {**base,'state':'UNAVAILABLE','reason':'해당 월의 전수 지표 보완 결과가 아직 게시되지 않았습니다.'}
    try:
        marker=json.loads(pointer.read_text(encoding='utf-8'))
        data=(directory/'metric-completion.json').read_bytes()
        digest=hashlib.sha256(data).hexdigest()
        if digest!=marker['sha256']:raise HTTPException(409,'보완 지표 checksum 불일치')
        packet=json.loads(data)
        if packet['report_month']!=start or marker['report_month']!=start:raise HTTPException(409,'보완 지표 기준월 불일치')
        validate_packet(packet)
        if packet['snapshot']!=view.name:
            return {**base,'state':'STALE','reason':'현재 검증본과 지표 검증본이 다릅니다. 이전 수치를 적용하지 않습니다.'}
        rows=[r for r in packet['channels'] if r['source_group']==source
              and (not station or r['station_code']==station) and (not item or r['item_code']==item)]
        if station_scope is not None:
            if 'include' in station_scope:rows=[r for r in rows if r['station_code'] in station_scope['include']]
            else:rows=[r for r in rows if r['station_code'] not in station_scope['exclude']]
        return {**base,'state':'AVAILABLE' if any(r['raw_rows'] for r in rows) else 'EMPTY_SCOPE','audit_sha256':digest,
                'generated_at':packet['generated_at'],'raw':raw_metrics(rows),
                'report_reference':report_metrics(rows),'channel_months':len(rows),
                'source_file_verification':packet['source_file_verification']}
    except HTTPException:raise
    except (OSError,KeyError,ValueError,TypeError):
        raise HTTPException(503,'보완 지표 기록을 읽을 수 없습니다.')
