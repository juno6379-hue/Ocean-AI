# 파일 역할: 시험 관측 원본의 형식과 필수 필드를 검증합니다.
"""F06 bounded wide-CSV parser. Preserve source semantics; never infer UTC or QC.

This parser emits source records for auditing. It does not authorize normalized
Parquet publication. Publication requires an evidence-backed release contract.
"""
import csv
import datetime as dt
import hashlib
from decimal import Decimal, InvalidOperation

ITEMS=('OTT','APR','ASP')
class SourceFormatError(ValueError):pass

def source_hash(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def parse_wide(stream, expected_station):
    """Return (CSV logical row number, raw row, observations, failure reason).

    Missing markers are specific to this family; all raw strings remain intact.
    Rows with malformed structure are quarantined, not silently truncated.
    """
    reader=csv.reader(stream,strict=True)
    try:header=next(reader)
    except StopIteration:raise SourceFormatError('EMPTY_FILE')
    required={'ID','Time',*(field for code in ITEMS for field in (code,code+'_QC1',code+'_QC2'))}
    if len(set(header))!=len(header):raise SourceFormatError('DUPLICATE_HEADER')
    if not required.issubset(header):raise SourceFormatError('MISSING_REQUIRED_HEADER')
    for number,values in enumerate(reader,2):
        if not values:yield number,values,[],'BLANK_ROW';continue
        if len(values)!=len(header):yield number,values,[],'ROW_WIDTH_MISMATCH';continue
        row=dict(zip(header,values))
        if row['ID']!=expected_station:yield number,values,[],'STATION_MISMATCH';continue
        try:
            stamp=dt.datetime.strptime(row['Time'],'%Y-%m-%d %H:%M:%S')
            if stamp.strftime('%Y-%m-%d %H:%M:%S')!=row['Time']:raise ValueError()
        except ValueError:yield number,values,[],'INVALID_TIME';continue
        observations=[];error=None
        for item in ITEMS:
            raw=row[item];missing=raw in ('','NaN','@')
            try:
                value=None if missing else Decimal(raw)
                if value is not None and not value.is_finite():raise InvalidOperation()
            except InvalidOperation:error='INVALID_VALUE';break
            observations.append({'station_id_raw':row['ID'],'item_code_raw':item,
                'observed_at_raw':row['Time'],'observed_at_local_naive':stamp,
                'value_raw_text':raw,'value_raw_numeric':str(value) if value is not None else None,
                'missing_marker':raw if missing else None,
                'source_qc_fields':{'QC1':row[item+'_QC1'],'QC2':row[item+'_QC2']},
                'source_record_number':number,'utc_time':None,'unit':None,'physical_sensor_id':None})
        yield number,values,observations if error is None else [],error

def release_blockers(contract, actual_sha256):
    missing=[]
    if contract.get('source_sha256')!=actual_sha256:missing.append('SOURCE_HASH_MISMATCH')
    for key in ['station_identity','item_mapping','units','timezone','qc_codebook','sensor_history','datum','role','inventory']:
        evidence=contract.get('evidence',{}).get(key,{})
        if evidence.get('status')!='VERIFIED' or not evidence.get('references'):missing.append(key.upper()+'_UNVERIFIED')
    if contract.get('multivariate_same_station_and_time') is not True:missing.append('MULTIVARIATE_IDENTITY_UNVERIFIED')
    return missing

def require_release(contract, actual_sha256):
    blockers=release_blockers(contract,actual_sha256)
    if blockers:raise SourceFormatError('RELEASE_BLOCKED: '+','.join(blockers))

def parse_dt_row(row, expected_ts_id, source_station_id):
    """Preserve one RTDB.DT row using the observed VW_WEB_OBS_DT mapping.

    The caller must supply an evidenced WEB_STATION(DATA_TYPE, OLD_ID) mapping.
    DT_TIDE is intentionally not used: DT_TIDE1 is the documented OTT column.
    Null IS_SIMULATED and unavailable QC are retained as unknown/absent.
    """
    if row.get('dt_ts_id') != expected_ts_id:
        raise SourceFormatError('STATION_MISMATCH')
    timestamp=row.get('dt_time')
    if isinstance(timestamp,dt.datetime):timestamp=timestamp.isoformat(sep=' ')
    try:
        stamp=dt.datetime.strptime(timestamp,'%Y-%m-%d %H:%M:%S')
        if stamp.strftime('%Y-%m-%d %H:%M:%S')!=timestamp:raise ValueError()
    except (TypeError,ValueError):raise SourceFormatError('INVALID_TIME')
    output=[]
    for field,item in [('dt_tide1','TIDE_LEVEL_OTT'),('dt_apress','AIR_PRES'),('dt_wspeed','WIND_SPEED')]:
        if field not in row:raise SourceFormatError('MISSING_REQUIRED_COLUMN')
        raw=row[field]
        try:
            value=None if raw is None else Decimal(str(raw))
            if value is not None and not value.is_finite():raise InvalidOperation()
        except InvalidOperation:raise SourceFormatError('INVALID_VALUE')
        output.append({'source_table':'RTDB.DT','station_id_raw':row['dt_ts_id'],
            'mapped_station_id':source_station_id,'source_field':field,'item_code_raw':item,
            'observed_at_raw':timestamp,'utc_time':None,
            'value_raw_numeric':str(value) if value is not None else None,
            'source_qc_fields':{},'source_qc_availability':'NOT_PROVIDED',
            'is_simulated_raw':row.get('is_simulated'),
            'physical_sensor_id':None,'unit':None})
    return output
