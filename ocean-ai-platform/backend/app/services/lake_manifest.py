"""계층별 명시적 manifest 선택. 재귀 검색·오류 무시·원천층 자동 학습을 금지한다."""
from pathlib import Path, PurePosixPath
import hashlib,json,re

class LakeManifestError(ValueError):pass

def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def select_files(root, layer, require_approved=False):
    root=Path(root).resolve()
    if layer not in {'raw','legacy','standardized'}:raise LakeManifestError('UNKNOWN_LAYER')
    manifest=root/'metadata'/layer/'manifest.json'
    if not manifest.is_file():raise LakeManifestError('MANIFEST_REQUIRED: '+str(manifest))
    if not manifest.resolve().is_relative_to(root):raise LakeManifestError('MANIFEST_OUTSIDE_ROOT')
    data=json.loads(manifest.read_text(encoding='utf8'))
    if data.get('schema_version')!=1 or data.get('layer')!=layer:raise LakeManifestError('MANIFEST_SCHEMA_OR_LAYER')
    if require_approved and (layer!='standardized' or data.get('status')!='APPROVED' or not data.get('approval_reference')):raise LakeManifestError('STANDARDIZED_RELEASE_NOT_APPROVED')
    if data.get('status') not in {'APPROVED','RAW_ONLY'}:raise LakeManifestError('LAYER_NOT_READABLE_PENDING_RECONCILIATION')
    if not isinstance(data.get('files'),list):raise LakeManifestError('FILES_LIST_REQUIRED')
    selected=[];seen=set()
    for entry in data['files']:
        rel=entry.get('path','');parts=PurePosixPath(rel)
        if not rel or '\\' in rel or ':' in rel or parts.is_absolute() or '..' in parts.parts:raise LakeManifestError('UNSAFE_PATH')
        if layer!='legacy' and (not parts.parts or parts.parts[0]!=layer):raise LakeManifestError('CROSS_LAYER_PATH')
        if layer=='legacy' and (not parts.parts or not (parts.parts[0]=='legacy' or parts.parts[0].startswith('year='))):raise LakeManifestError('CROSS_LAYER_PATH')
        p=(root/rel).resolve()
        if not p.is_relative_to(root):raise LakeManifestError('PATH_OUTSIDE_ROOT')
        key=str(p).casefold()
        if key in seen:raise LakeManifestError('DUPLICATE_FILE')
        seen.add(key)
        if p.suffix!='.parquet' or not p.is_file():raise LakeManifestError('PARQUET_MISSING')
        if not re.fullmatch('[0-9a-f]{64}',entry.get('sha256','')):raise LakeManifestError('SHA256_REQUIRED')
        if checksum(p)!=entry['sha256']:raise LakeManifestError('FILE_HASH_MISMATCH')
        if type(entry.get('rows')) is not int or entry['rows']<0:raise LakeManifestError('ROW_COUNT_REQUIRED')
        selected.append((p,entry['rows']))
    return selected

def load_observations(root,layer,station_id=None,variable_code=None):
    """분석 소비자는 승인 표준층만 허용. 센서 혼합·중복·값 충돌을 임의 해소하지 않는다."""
    import pandas as pd
    import pyarrow.parquet as pq
    import numpy as np
    paths=select_files(root,layer,require_approved=True);frames=[]
    columns=['station_id','sensor_id','variable_code','timestamp_utc','value_raw']
    for p,count in paths:
        pf=pq.ParquetFile(p)
        if pf.metadata.num_rows!=count:raise LakeManifestError('ROW_COUNT_MISMATCH')
        if not set(columns)<=set(pf.schema_arrow.names):raise LakeManifestError('STANDARD_SCHEMA_REQUIRED')
        d=pf.read(columns=columns).to_pandas()
        if station_id is not None:d=d[d.station_id==station_id]
        if variable_code is not None:d=d[d.variable_code==variable_code.upper()]
        frames.append(d)
    if not frames:return pd.DataFrame(columns=columns)
    d=pd.concat(frames,ignore_index=True)
    if d.empty:return d
    if d[columns[:3]].isna().any().any() or (d[columns[:3]].astype(str).apply(lambda c:c.str.strip()=='')).any().any():raise LakeManifestError('IDENTITY_REQUIRED')
    if not isinstance(d.timestamp_utc.dtype,pd.DatetimeTZDtype) or str(d.timestamp_utc.dt.tz)!='UTC' or d.timestamp_utc.isna().any():raise LakeManifestError('UTC_REQUIRED')
    if d.duplicated(columns[:4]).any():raise LakeManifestError('DUPLICATE_OBSERVATION_KEY')
    if (d.groupby(['station_id','variable_code']).sensor_id.nunique()>1).any():raise LakeManifestError('MULTIPLE_SENSORS_REQUIRE_EXPLICIT_SPLIT')
    values=pd.to_numeric(d.value_raw,errors='raise')
    if np.isinf(values.to_numpy(dtype=float)).any():raise LakeManifestError('INFINITE_VALUE')
    d['value_raw']=values
    return d.sort_values('timestamp_utc')
