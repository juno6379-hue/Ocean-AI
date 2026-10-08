"""원천층 QC 민감도 파일럿. 결과는 검토 후보이며 표준화/학습 승인이 아니다.

가이드북 PDF 81/82쪽의 기존/개선안 범위를 분리한다. 단위와 센서 이력이
미확정이므로 값의 단위 변환이나 원천 QC 해석을 하지 않는다.
"""
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from app.services.lake_manifest import select_files, checksum

VERSION = 'raw-qc-screening-v2-guide-2023-12'
GUIDE_SHA256 = 'd1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9'
# 단위는 검증된 원천 단위가 아니라 아래 민감도 비교의 명시적 가정이다.
RULES = {
 'OTT': {'unit_assumption':'cm', 'old':[-300,1300], 'proposal':[-300,1300], 'flat_seconds':7200, 'spike':{}},
 'WTP': {'unit_assumption':'degC', 'old':[-2.5,35], 'proposal':[-2,40], 'flat_seconds':86400, 'spike':{60:0.6,300:1.4,600:2.0,1800:3.5}},
 'SAL': {'unit_assumption':'psu', 'old':[0,40], 'proposal':[0,41], 'flat_seconds':86400, 'spike':{60:0.3,300:0.8,600:1.1,1800:1.9}},
 'APR': {'unit_assumption':'hPa', 'old':[850,1060], 'proposal':[850,1060], 'flat_seconds':10800, 'spike':{60:1.6,300:3.5,600:5.0,1800:8.6}},
 'ASP': {'unit_assumption':'m/s', 'old':[0,60], 'proposal':[0,60], 'flat_seconds':10800, 'spike':{}},
}
ALIASES = {'dt_tide1':'OTT','dt_apress':'APR','dt_wspeed':'ASP'}

def screen(frame, rule):
    """단일 원천·관측소·항목에 적용. 센서 경계/결측/중복/시간 역전에서 연속검사 초기화.

    고정값은 관측된 중앙 간격의 1.5배 이하로 이어진 동일값 구간에서
    기준시간 *초과* 시점부터 후보. 미확인 센서의 숨은 교체는 검출 불가.
    튐값은 표에 명시된 정확한 실제 시간차만 사용하며 보간하지 않는다.
    """
    d=frame.copy().reset_index(drop=True)
    for col in ['source_id','station_id_raw','item_code_raw']:
        if d[col].nunique(dropna=False)!=1: raise ValueError('MIXED_SOURCE_SERIES')
    t=pd.to_datetime(d.source_clock_naive, errors='coerce')
    x=pd.to_numeric(d.value_numeric,errors='coerce')
    valid=pd.Series(np.isfinite(x),index=d.index) & d.value_status.eq('NUMERIC_UNREVIEWED')
    delta=t.diff().dt.total_seconds()
    cadence=float(delta[delta>0].median()) if (delta>0).any() else None
    duplicate=t.notna() & t.duplicated(keep=False)
    same_sensor=d.sensor_id.fillna('<UNKNOWN>').eq(d.sensor_id.shift().fillna('<UNKNOWN>'))
    continuity=valid & valid.shift(fill_value=False) & t.notna() & t.shift().notna() & same_sensor & ~duplicate & ~duplicate.shift(fill_value=False) & delta.gt(0)
    continuity &= delta.le(cadence*1.5) if cadence else False
    d['time_parse_invalid']=t.isna()
    d['duplicate_clock']=duplicate
    d['clock_reversal']=delta.lt(0)
    d['gap_candidate']=delta.gt(cadence*1.5) if cadence else False
    d['numeric_available']=valid
    for name in ['old','proposal']:
        lo,hi=rule[name]
        d['range_'+name]=np.where(~valid,'NOT_EVALUATED',np.where(x.lt(lo)|x.gt(hi),'CANDIDATE','NO_TRIGGER'))
    # 결측을 사이에 둔 동일값을 하나의 고정 구간으로 합치지 않는다.
    equal=continuity & x.eq(x.shift())
    run=(~equal).cumsum()
    start=t.groupby(run).transform('first')
    elapsed=(t-start).dt.total_seconds()
    d['flat_elapsed_seconds']=elapsed.where(valid & t.notna())
    d['flat_candidate']=valid & elapsed.gt(rule['flat_seconds'])
    threshold=delta.map(rule['spike'])
    eligible=continuity & threshold.notna()
    d['spike_proposal']=np.where(~eligible,'NOT_EVALUATED',np.where(x.diff().abs().gt(threshold),'CANDIDATE','NO_TRIGGER'))
    d['candidate_any']=d.range_old.eq('CANDIDATE')|d.range_proposal.eq('CANDIDATE')|d.flat_candidate|d.spike_proposal.eq('CANDIDATE')
    d['qc_decision']='NOT_EVALUATED_SOURCE_CONTRACT_UNVERIFIED'
    d['screening_version']=VERSION
    d['assumed_unit_for_screening']=rule['unit_assumption']
    return d,cadence

def run(lake, output, guide):
    # 사용자가 채택한 개편판 파일 자체를 고정해 다른 판본의 묵시 적용을 막는다.
    if checksum(guide) != GUIDE_SHA256: raise ValueError('GUIDE_HASH_MISMATCH')
    lake=Path(lake); output=Path(output)
    if output.exists(): raise ValueError('OUTPUT_ALREADY_EXISTS_USE_NEW_RUN_DIRECTORY')
    manifest_before=checksum(lake/'metadata/raw/manifest.json')
    selected=select_files(lake,'raw'); frames=[]; used=[]
    for path,rows in selected:
        f=pq.ParquetFile(path)
        if f.metadata.num_rows!=rows: raise ValueError('ROW_COUNT_MISMATCH')
        d=f.read().to_pandas()
        keep=d.item_code_raw.isin(set(RULES)|set(ALIASES))
        if keep.any():
            frames.append(d.loc[keep]);used.append({'path':str(path.relative_to(lake)), 'sha256':checksum(path),'rows_selected':int(keep.sum())})
    if not frames: raise ValueError('EMPTY_PILOT_SCOPE')
    source=pd.concat(frames,ignore_index=True)
    results=[]; summaries=[]
    for (sid,station,item),g in source.groupby(['source_id','station_id_raw','item_code_raw'],dropna=False):
        # 파일명 순서 대신 원천 레코드 순서를 사용해 시간 역전을 숨기지 않는다.
        g=g.sort_values('source_record_number',kind='stable')
        if g.source_record_number.duplicated().any(): raise ValueError('DUPLICATE_SOURCE_RECORD')
        r,cadence=screen(g,RULES[ALIASES.get(item,item)])
        results.append(r)
        summaries.append({'source_id':sid,'station_id_raw':station,'item':item,'rows':len(r),'numeric':int(r.numeric_available.sum()),'missing_or_unresolved':int((~r.numeric_available).sum()),'observed_median_seconds':cadence,'range_old':int(r.range_old.eq('CANDIDATE').sum()),'range_proposal':int(r.range_proposal.eq('CANDIDATE').sum()),'flat_candidate':int(r.flat_candidate.sum()),'spike_candidate':int(r.spike_proposal.eq('CANDIDATE').sum()),'spike_evaluated':int(r.spike_proposal.ne('NOT_EVALUATED').sum()),'candidate_any':int(r.candidate_any.sum()),'gap_candidate':int(r.gap_candidate.sum()),'duplicate_clock':int(r.duplicate_clock.sum()),'clock_reversal':int(r.clock_reversal.sum()),'qc_valid_count':None})
    d=pd.concat(results,ignore_index=True)
    if checksum(lake/'metadata/raw/manifest.json') != manifest_before: raise ValueError('INPUT_MANIFEST_CHANGED')
    output.mkdir(parents=True)
    pq.write_table(pa.Table.from_pandas(d,preserve_index=False),output/'record-screening.parquet',compression='zstd')
    # 원천 플래그 문자열 그대로 교차 집계. G/B를 정상/오류로 번역하지 않는다.
    d['month_raw_clock']=pd.to_datetime(d.source_clock_naive).dt.strftime('%Y-%m')
    cross=d.groupby(['source_id','item_code_raw','month_raw_clock','qc1_raw','qc2_raw','candidate_any'],dropna=False).size().reset_index(name='rows')
    cross.to_json(output/'source-flag-cross-tab.json',orient='records',force_ascii=False,indent=2)
    # 검토 큐는 후보 행의 연속 원천번호 구간. 센서/시간 틈에서 추가 분리한다.
    intervals=[]
    for (sid,item),g in d.groupby(['source_id','item_code_raw']):
        breaks=(~g.candidate_any)|g.gap_candidate|g.duplicate_clock|g.clock_reversal|g.source_record_number.diff().ne(1)|g.sensor_id.fillna('?').ne(g.sensor_id.shift().fillna('?'))
        for _,seg in g[g.candidate_any].groupby(breaks.cumsum()):
            intervals.append({'source_id':sid,'item':item,'start_raw_clock':str(seg.source_clock_naive.iloc[0]),'end_raw_clock':str(seg.source_clock_naive.iloc[-1]),'first_source_record':int(seg.source_record_number.iloc[0]),'last_source_record':int(seg.source_record_number.iloc[-1]),'candidate_rows':len(seg),'review_status':'PENDING','decision':None,'reviewer':None,'evidence':[]})
    (output/'review-queue.json').write_text(json.dumps(intervals,ensure_ascii=False,indent=2),encoding='utf8')
    summary={'version':VERSION,'created_at':datetime.now(timezone.utc).isoformat(),'status':'SCREENING_ONLY_NOT_RELEASED','input_manifest_sha256':checksum(lake/'metadata/raw/manifest.json'),'input_files':used,'rules':RULES,'guide_edition':'2023-12 revised; user-selected working baseline','guide_path':str(guide),'flat_policy':'old-guide duration, strict > elapsed; screening interpretation, not exact operational reproduction','alias_policy':'dt_tide1 uses generic tide thresholds only; not an OTT sensor identification','guide_pdf_pages':[81,82,83,84,85,87,89,93,94],'guide_sha256':'d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9','rows':len(d),'candidate_rows':int(d.candidate_any.sum()),'review_intervals':len(intervals),'qc_evaluated_count':0,'qc_valid_count':None,'series':summaries,'not_evaluated':['approved_physical_qc: historical item/unit/sensor contract missing','source_flag_agreement: historical QC code mapping missing','seasonal/statistical: approved baseline missing','tidal_residual: matching prediction and datum missing','multivariate: source/sensor contemporaneity unverified','missing_rate: nominal cadence unverified'],'limitations':['Source clock remains timezone-naive; no UTC conversion.','Flat checks use observed cadence; unknown sensor replacement may be crossed.','No-trigger is not GOOD. No correction, deletion, interpolation or release.','Guide proposal is not evidence of historical operational use.','Exact-interval spike check excludes jitter and undocumented intervals.']}
    if pq.ParquetFile(output/'record-screening.parquet').metadata.num_rows!=len(source): raise ValueError('OUTPUT_ROW_RECONCILIATION_FAILED')
    summary['outputs']=[{'path':p.name,'sha256':checksum(p)} for p in sorted(output.iterdir()) if p.is_file()]
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lake',required=True);p.add_argument('--output',required=True);p.add_argument('--guide',required=True)
    a=p.parse_args();s=run(a.lake,a.output,a.guide);print(json.dumps({k:s[k] for k in ['rows','candidate_rows','review_intervals','status']},ensure_ascii=False))
