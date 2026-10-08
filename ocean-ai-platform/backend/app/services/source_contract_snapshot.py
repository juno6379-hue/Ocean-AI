"""Freeze reviewed source dependencies inside a dataset's immutable content hash.

Draft receipts can be copied and reviewed, but neither self-declared APPROVED
nor a legacy dataset bypasses the live source approval ledger. Raw data is read
and hashed; only bounded JSON dependencies are copied. No human approval is made.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,re,tempfile

SCHEMA='event-evidence-dataset-2'
MAX_BYTES=64*1024*1024
ROLES={'SOURCE_CONTRACT','SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY','REVIEW_CANDIDATES'}
DEFAULT_ROOTS=('D:/AI_Observation/source','D:/AI_Observation/data_lake','D:/AI_Observation/metadata','D:/AI_Observation/outputs')


class DependencyError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)


def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()


def guarded_path(path,roots,require_file=False):
    if not isinstance(path,(str,Path)) or not str(path):raise DependencyError('DEPENDENCY_PATH_INVALID')
    if not isinstance(roots,(list,tuple)) or not roots or any(not isinstance(r,(str,Path)) for r in roots):raise DependencyError('DEPENDENCY_ROOTS_INVALID')
    original=Path(path);resolved=original.resolve()
    if not any(resolved.is_relative_to(Path(r).resolve()) for r in roots):raise DependencyError('DEPENDENCY_PATH_OUTSIDE_ALLOWED_ROOTS')
    for current in [original.absolute(),*original.absolute().parents]:
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():raise DependencyError('DEPENDENCY_REPARSE_PATH')
    if require_file and not resolved.is_file():raise DependencyError('DEPENDENCY_NOT_REGULAR_FILE')
    return resolved


def source_roots():
    value=os.environ.get('SOURCE_CONTRACT_ALLOWED_ROOTS')
    return [str(Path(p).resolve()) for p in (json.loads(value) if value else DEFAULT_ROOTS)]


def canonical_bytes(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,default=str).encode('utf-8')


def read_bounded(path,roots,expected=None):
    resolved=guarded_path(path,roots,True)
    if not resolved.is_file() or resolved.suffix.lower()!='.json':raise DependencyError('DEPENDENCY_NOT_JSON_FILE')
    before=resolved.stat()
    if before.st_size>MAX_BYTES:raise DependencyError('DEPENDENCY_TOO_LARGE')
    raw=resolved.read_bytes();after=resolved.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise DependencyError('DEPENDENCY_CHANGED_DURING_READ')
    sha=sha_bytes(raw)
    if expected is not None and (not re.fullmatch('[0-9a-f]{64}',str(expected)) or expected!=sha):raise DependencyError('DEPENDENCY_HASH_MISMATCH')
    def unique(items):
        result={}
        for key,value in items:
            if key in result:raise DependencyError('DEPENDENCY_DUPLICATE_JSON_KEY')
            result[key]=value
        return result
    def invalid(value):raise DependencyError('DEPENDENCY_NONFINITE_JSON')
    value=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)
    if not isinstance(value,dict):raise DependencyError('DEPENDENCY_OBJECT_REQUIRED')
    return value,raw,sha


def immutable_copy(root,sha,raw):
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) or not isinstance(raw,bytes) or sha_bytes(raw)!=sha:raise DependencyError('IMMUTABLE_CONTENT_HASH_INVALID')
    root=guarded_path(root,[root]);folder=guarded_path(root/'dependencies',[root]);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(sha+'.json')
    if path.exists():
        if path.read_bytes()!=raw:raise DependencyError('IMMUTABLE_DEPENDENCY_CHANGED')
        return 'dependencies/'+sha+'.json'
    # Exclusive final creation is atomic with respect to competing same-hash
    # writers; a transient incomplete file never replaces an existing receipt.
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=folder,suffix='.tmp',delete=False) as f:
            tmp=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
        try:os.link(tmp,path)
        except FileExistsError:
            if path.read_bytes()!=raw:raise DependencyError('IMMUTABLE_DEPENDENCY_CHANGED')
    finally:
        if tmp and tmp.exists():tmp.unlink()
    return 'dependencies/'+sha+'.json'


def source_authority(db,receipt,sha):
    if receipt.get('schema_version')!='source-semantics-identity-period-event-1' or receipt.get('source_contract_schema')!='source_contract_v2':
        raise DependencyError('SOURCE_CONTRACT_V2_APPROVED_EXPORT_REQUIRED')
    from app.services.source_contract_authority import verify_approved_receipt
    return verify_approved_receipt(db,receipt,sha,verify_sources=True)


def protocol_authority(db,receipt,sha,role):
    from app.ml.protocols import validate_approved_protocol
    return validate_approved_protocol(db,receipt,sha,role)


def dependency_review(db,receipt,sha,role):
    try:
        if role=='SOURCE_CONTRACT':return source_authority(db,receipt,sha),[]
        if role=='REVIEW_CANDIDATES':return None,['REVIEW_CANDIDATES_NOT_APPROVED_OBSERVATION_MEMBERSHIP']
        return protocol_authority(db,receipt,sha,role),[]
    except (ValueError,ImportError) as exc:
        return None,[getattr(exc,'code',str(exc) or 'DEPENDENCY_APPROVAL_UNVERIFIED')]


def freeze_dependencies(db,snapshot,specs,root,roots=None):
    if not isinstance(specs,list) or any(not isinstance(s,dict) or set(s)!={'role','path','sha256'} for s in specs):raise DependencyError('DEPENDENCY_SPEC_INVALID')
    if len(specs)>128:raise DependencyError('DEPENDENCY_COUNT_EXCEEDED')
    roots=source_roots() if roots is None else roots
    result=dict(snapshot);sources=[];protocols=[];reviews=[];errors=[];seen=set()
    for spec in specs:
        role=spec.get('role')
        if role not in ROLES:raise DependencyError('DEPENDENCY_ROLE_INVALID')
        receipt,raw,sha=read_bounded(spec['path'],roots,spec['sha256'])
        if sha in seen:raise DependencyError('DUPLICATE_DEPENDENCY')
        seen.add(sha)
        authority,issues=dependency_review(db,receipt,sha,role)
        path=immutable_copy(root,sha,raw)
        item={'role':role,'path':path,'sha256':sha,'contract_id':receipt.get('contract_id'),
              'approval_receipt':authority,'review_errors':issues}
        (sources if role=='SOURCE_CONTRACT' else reviews if role=='REVIEW_CANDIDATES' else protocols).append(item)
        errors.extend(role+':'+x for x in issues)
    from app.services.source_contract_authority import SOURCE_ROOT
    result.update(schema_version=SCHEMA,clock_contract='UTC_WITH_EXPLICIT_OFFSET',
        source_contract_root=str(Path(root).resolve()),verified_source_roots=[str(SOURCE_ROOT.resolve())],
        source_contracts=sorted(sources,key=lambda x:x['sha256']),frozen_protocol_dependencies=sorted(protocols,key=lambda x:x['role']),
        draft_review_dependencies=sorted(reviews,key=lambda x:x['sha256']))
    if not sources:errors.append('SOURCE_CONTRACT_DEPENDENCIES_MISSING')
    for role in ['SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY']:
        if sum(x['role']==role for x in protocols)!=1:errors.append(role+'_ONE_FROZEN_DEPENDENCY_REQUIRED')
    result['validation_errors']=sorted(set(result.get('validation_errors',[])+errors))
    result=normalize_utc_fields(result)
    result=overlay_proofs(db,result)
    result['validation_errors']=sorted(set(result['validation_errors']+protocol_binding_errors(result)))
    return result


def normalize_utc_fields(value):
    utc_fields={'timestamp','timestamp_utc','period_start','period_end','event_start','event_end','window_start','window_end','available_at'}
    if isinstance(value,list):return [normalize_utc_fields(v) for v in value]
    if not isinstance(value,dict):return value
    result={}
    for key,v in value.items():
        if key in utc_fields and isinstance(v,datetime):
            # Existing ORM/service fields explicitly represent UTC even though
            # PostgreSQL legacy columns are timestamp without time zone.
            result[key]=(v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)).isoformat()
        else:result[key]=normalize_utc_fields(v)
    return result


def overlay_proofs(db,snapshot):
    from app.models.source_observation_binding import SourceObservationBinding
    root=Path(snapshot['source_contract_root']);proofs={};errors=[]
    for dep in snapshot['source_contracts']:
        receipt,_,sha=read_bounded(root/dep['path'],[root],dep['sha256'])
        if dep.get('review_errors') or not dep.get('approval_receipt'):continue
        for oid,proof in receipt.get('observations',{}).items():
            if oid in proofs:errors.append('AMBIGUOUS_SOURCE_CONTRACT:'+oid)
            proofs[oid]=proof
    for record in snapshot.get('records',[]):
        oid=record['id'];proof=proofs.get(oid)
        if not proof:
            errors.append('SOURCE_CONTRACT_OBSERVATION_COVERAGE_MISSING:'+oid);continue
        binding=db.get(SourceObservationBinding,oid)
        if not binding or binding.payload!=proof or binding.receipt_sha256 not in {d['sha256'] for d in snapshot['source_contracts']}:
            errors.append('STANDARD_OBSERVATION_SOURCE_BINDING_MISSING_OR_CHANGED:'+oid);continue
        raw=record.get('raw') or {}
        pairs={'canonical_station_id':record['station_id'],'canonical_sensor_id':record['sensor_id'],
               'standard_variable':record['variable_code'],'unit':record['unit'],
               'source_group':raw.get('source_system'),'source_item_code':raw.get('source_item_code'),
               'source_qc_raw':raw.get('qc_flag'),'source_mqc_raw':raw.get('mqc_flag')}
        if any(proof.get(k)!=v for k,v in pairs.items()):
            errors.append('SOURCE_CONTRACT_EXISTING_RECORD_MISMATCH:'+oid);continue
        depth={'step':raw.get('water_step'),'from':raw.get('from_depth'),'to':raw.get('to_depth')}
        if canonical_bytes(proof.get('depth'))!=canonical_bytes(depth):
            errors.append('SOURCE_CONTRACT_DEPTH_MISMATCH:'+oid);continue
        for key in ['source_station_code','physical_sensor_id','source_sha256','parquet_sha256','source_row_locator',
                'source_station_literal','source_item_literal','source_identifier_transform']:
            if not proof.get(key):errors.append('SOURCE_CONTRACT_PROVENANCE_MISSING:'+oid+':'+key)
            raw[key]=proof.get(key)
        raw['source_timezone_name']=proof.get('timezone');raw['source_clock_semantics']=proof.get('source_clock_semantics')
        for key in ['typed_payload','rule_qc']:
            if key in proof:record[key]=proof[key]
        if 'source_column_map' in proof:raw['source_column_map']=proof['source_column_map']
        if proof.get('quantity_kind')=='SCALAR':
            record['typed_payload']={'representation':'SCALAR','value':proof['value']}
        if proof.get('timestamp_utc')!=record.get('timestamp') or (proof.get('quantity_kind')=='SCALAR' and str(proof.get('value'))!=str(record.get('value_standard'))):
            # Decimal comparison allows canonical numeric rendering, but never
            # a different source value or a changed observation instant.
            from decimal import Decimal,InvalidOperation
            try:
                same_time=datetime.fromisoformat(proof['timestamp_utc'])==datetime.fromisoformat(record['timestamp'])
                same_value=proof.get('quantity_kind')!='SCALAR' or Decimal(str(proof['value']))==Decimal(str(record['value_standard']))
            except (KeyError,TypeError,ValueError,InvalidOperation):same_time=same_value=False
            if not same_time or not same_value:errors.append('SOURCE_CONTRACT_TIME_OR_VALUE_MISMATCH:'+oid)
        reviewed_receive=proof.get('source_receive_timestamp_utc')
        if raw.get('receive_time') is not None or reviewed_receive is not None:
            # This ORM value was populated only from the reviewed UTC receive
            # clock. Keep its original literal and clock policy in the binding.
            try:
                saved=raw['receive_time']
                if isinstance(saved,str):saved=datetime.fromisoformat(saved)
                if saved.tzinfo is None:saved=saved.replace(tzinfo=timezone.utc)
                if saved!=datetime.fromisoformat(reviewed_receive):errors.append('SOURCE_RECEIVE_TIME_CHANGED:'+oid)
            except (AttributeError,TypeError,ValueError):errors.append('SOURCE_RECEIVE_TIME_CHANGED:'+oid)
        raw['receive_time']=reviewed_receive
        for key in ['source_receive_time_raw','source_receive_timestamp_utc','source_receive_clock_policy']:
            raw[key]=proof.get(key)
        if 'source_receive_timezone' in proof:raw['source_receive_timezone']=proof['source_receive_timezone']
        record['raw']=raw
        # The datastore's explicitly UTC observation timestamp is the existing
        # origin policy. A later source release cannot be made earlier by a
        # FeatureProvenance row that merely declares an earlier availability.
        for feature in record.get('features',[]):
            fid=feature['feature_id'];provenance=feature.get('provenance') or {}
            source_ids=provenance.get('source_observation_ids')
            if not isinstance(source_ids,list) or not source_ids:
                errors.append('SOURCE_FEATURE_MEMBERSHIP_UNVERIFIED:'+oid+':'+fid);continue
            for sid in source_ids:
                if not isinstance(sid,str) or not sid:
                    errors.append('SOURCE_FEATURE_CONTRACT_OR_BINDING_MISSING:'+oid+':'+fid+':INVALID_SOURCE_ID');continue
                source=proofs.get(sid);source_binding=db.get(SourceObservationBinding,sid)
                if not source or not source_binding or source_binding.payload!=source or source_binding.receipt_sha256 not in {d['sha256'] for d in snapshot['source_contracts']}:
                    errors.append('SOURCE_FEATURE_CONTRACT_OR_BINDING_MISSING:'+oid+':'+fid+':'+str(sid));continue
                try:
                    origin=datetime.fromisoformat(record['timestamp'])
                    declared=datetime.fromisoformat(provenance['available_at'])
                    if origin.tzinfo is None or declared.tzinfo is None:raise ValueError()
                    for field in ['available_at','qc_available_at']:
                        available=datetime.fromisoformat(source[field])
                        if available.tzinfo is None:raise ValueError()
                        if available>declared:errors.append('SOURCE_FEATURE_AVAILABLE_AFTER_DECLARED_TIME:'+oid+':'+fid+':'+sid+':'+field)
                        if available>origin:errors.append('CLOCK_ORIGIN_POLICY_REVIEW_REQUIRED:'+oid+':'+fid+':'+sid+':'+field)
                except (KeyError,TypeError,ValueError):errors.append('SOURCE_FEATURE_AS_OF_CLOCK_UNVERIFIED:'+oid+':'+fid+':'+str(sid))
    snapshot['validation_errors']=sorted(set(snapshot['validation_errors']+errors))
    return snapshot


def protocol_binding_errors(snapshot):
    """Bind fixed membership and periods to this exact split, before approval."""
    from app.ml.comparison_runner import digest,clock
    errors=[];bodies={};root=Path(snapshot['source_contract_root'])
    for dep in snapshot.get('frozen_protocol_dependencies',[]):
        body,_,_=read_bounded(root/dep['path'],[root],dep['sha256'])
        bodies[dep['role']]=body
    split=snapshot.get('split');protocol=bodies.get('SPLIT_PROTOCOL')
    if protocol:
        try:
            if protocol['dataset_ids'][split]!=snapshot['dataset_id']:errors.append('SPLIT_PROTOCOL_DATASET_ID_MISMATCH')
            if protocol['member_ids_sha256'][split]!=digest(sorted(r['id'] for r in snapshot['records'])):errors.append('SPLIT_PROTOCOL_MEMBERSHIP_MISMATCH')
            span=protocol['periods'][split]
            if clock(span['start'],True)!=clock(snapshot['period_start'],True) or clock(span['end'],True)!=clock(snapshot['period_end'],True):errors.append('SPLIT_PROTOCOL_PERIOD_MISMATCH')
        except (KeyError,TypeError,ValueError):errors.append('SPLIT_PROTOCOL_BINDING_INCOMPLETE')
    for role,body in bodies.items():
        if any(r['variable_code']!=body.get('target_variable') or r['unit']!=body.get('unit') for r in snapshot['records']):errors.append(role+'_TARGET_OR_UNIT_MISMATCH')
    evaluation=bodies.get('EVALUATION_PROTOCOL')
    if evaluation and set(evaluation.get('feature_ids',[]))!={f['feature_id'] for r in snapshot['records'] for f in r['features']}:
        errors.append('EVALUATION_PROTOCOL_FEATURES_MISMATCH')
    return sorted(set(errors))


def hash_source_file(path,roots,expected):
    path=guarded_path(path,roots,True)
    before=path.stat();sha=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):sha.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or sha.hexdigest()!=expected:raise DependencyError('SOURCE_BYTES_HASH_MISMATCH')
    return before.st_size


def create_candidate_snapshot(parquet_path,manifest_path,manifest_sha256,source_group,scopes,root,limit=500,roots=None):
    """Read real raw rows without creating training memberships or approvals.

    The exact locator stays tied to the full Parquet hash. SQLPlus padding is
    retained separately from the census code. No timestamp is converted before
    its observed-role/timezone evidence has been approved.
    """
    import pyarrow.parquet as pq
    from app.services.source_contract_review import exact_scope_key,GRAIN
    roots=source_roots() if roots is None else roots
    if type(limit) is not int or not 1<=limit<=5000:raise DependencyError('CANDIDATE_LIMIT_INVALID')
    if not 1<=len(scopes)<=128 or any(set(s)!=set(GRAIN) or s.get('source_group')!=source_group for s in scopes):raise DependencyError('CANDIDATE_EXACT_SCOPE_REQUIRED')
    wanted={exact_scope_key(s) for s in scopes}
    if len(wanted)!=len(scopes):raise DependencyError('CANDIDATE_DUPLICATE_SCOPE')
    manifest,_,msha=read_bounded(manifest_path,roots,manifest_sha256)
    parquet=guarded_path(parquet_path,roots,True);pf=pq.ParquetFile(parquet)
    names=set(pf.schema_arrow.names)
    if {'station_raw','item_raw','time_raw','value_raw'}<=names:
        if source_group!='GD_OBS_ST_MONTHLY' or manifest.get('status')!='RAW_PARSED_RECONCILED':raise DependencyError('SQLPLUS_SOURCE_MANIFEST_UNCONFIRMED')
        entries=[f for f in manifest.get('files',[]) if (Path(manifest_path).parent.parent.parent/f.get('path','')).resolve()==parquet]
        if len(entries)!=1:raise DependencyError('PARQUET_MANIFEST_LINEAGE_MISMATCH')
        desc=entries[0];psha=desc['sha256'];expected_rows=desc['rows']
        columns={'station':'station_raw','item':'item_raw','time':'time_raw','value':'value_raw','qc':'qc_raw','mqc':'mq_raw','n1':'n1_aqc_raw'}
        adapter='MONTHLY_SQLPLUS_RAW';identifier={'station':'STRIP_SQLPLUS_PADDING','item':'STRIP_SQLPLUS_PADDING'}
    elif {'OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE'}<=names:
        if manifest.get('status')!='VERIFIED' or manifest.get('source_system')!=source_group or Path(manifest.get('raw_path','')).resolve()!=parquet:raise DependencyError('PARQUET_MANIFEST_LINEAGE_MISMATCH')
        psha=manifest['raw_sha256'];expected_rows=manifest['raw_rows']
        columns={'station':'OBS_POST_ID','item':'OBS_ITEM_CODE','time':'OBS_TIME','value':'OBS_VALUE','qc':'QC_FLAG','mqc':'MQC_FLAG','n1':'N1_AQC_FLAG','received':'RECEIVE_TIME','step':'WATER_STEP','from':'FR_DEPTH' if 'FR_DEPTH'in names else 'FROM_DEPTH','to':'TO_DEPTH'}
        adapter='MONTHLY_SOURCE_STRINGS';identifier={'station':'IDENTITY','item':'IDENTITY'}
    else:raise DependencyError('RAW_PARQUET_ADAPTER_UNSUPPORTED')
    size=hash_source_file(parquet,roots,psha)
    if pf.metadata.num_rows!=expected_rows:raise DependencyError('PARQUET_MANIFEST_ROWCOUNT_MISMATCH')
    rows=[];selected=[c for c in columns.values() if c in names];reached_limit=False
    for group in range(pf.num_row_groups):
        offset=0
        for batch in pf.iter_batches(row_groups=[group],columns=selected,batch_size=4096):
            for index,row in enumerate(batch.to_pylist()):
                values={k:row.get(v) for k,v in columns.items()}
                station,item=values['station'],values['item']
                if not isinstance(station,str) or not isinstance(item,str) or not isinstance(values['time'],str):continue
                if adapter=='MONTHLY_SQLPLUS_RAW':station,item=station.strip(),item.strip()
                try:month=datetime.fromisoformat(values['time']).strftime('%Y-%m')
                except ValueError:continue
                grain=dict(source_group=source_group,station_code=station,item_code=item,month=month,
                    depth_step=values.get('step'),depth_from=values.get('from'),depth_to=values.get('to'))
                key=exact_scope_key(grain)
                if key not in wanted:continue
                locator=f'parquet_row_group={group};row_index={offset+index}'
                oid='candidate-'+sha_bytes((psha+'|'+locator).encode())
                candidate={'observation_id':oid,'exact_scope_key':key,'source_group':source_group,
                    'source_station_code':station,'source_item_code':item,'source_month':month,
                    'source_station_literal':values['station'],'source_item_literal':values['item'],
                    'source_identifier_transform':identifier,'source_time_raw':values['time'],
                    'source_value_raw':values['value'],'source_qc_raw':values.get('qc'),'source_mqc_raw':values.get('mqc'),
                    'source_n1_aqc_raw':values.get('n1'),'source_receive_time_raw':values.get('received'),
                    'source_receive_timestamp_utc':None,'source_receive_clock_policy':None,
                    'depth':{'step':values.get('step'),'from':values.get('from'),'to':values.get('to')},
                    'source_row_locator':locator,'source_sha256':manifest['source_sha256'],'parquet_sha256':psha,
                    'source_manifest_sha256':msha,'physical_sensor_id':None,'sensor_episode_id':None,
                    'canonical_station_id':None,'canonical_sensor_id':None,'standard_variable':None,
                    'timezone':None,'source_clock_semantics':None,'observation_role':None,'source_unit':None,'unit':None,
                    'quantity_transform':None,'effective_start':None,'effective_end':None,'available_at':None,
                    'event_id':None,'qc_rule_version':None,'qc_available_at':None,'training_value_status':None,
                    'validation_errors':['IDENTITY_PERIOD_UNIT_CLOCK_QC_AS_OF_EVENT_APPROVAL_REQUIRED']}
                if adapter=='MONTHLY_SOURCE_STRINGS' and 'FR_DEPTH' in names:
                    candidate['source_column_map']={'depth_from':'FR_DEPTH'}
                rows.append(candidate)
                if len(rows)>=limit:reached_limit=True;break
            offset+=batch.num_rows
            if reached_limit:break
        if reached_limit:break
    snapshot={'schema_version':'raw-source-candidate-snapshot-1','status':'DRAFT','approved':False,
        'training_eligible':False,'operational_membership_count':0,'source_group':source_group,'source_adapter':adapter,
        'source_manifest':{'path':str(Path(manifest_path).resolve()),'sha256':msha},
        'parquet':{'path':str(parquet),'sha256':psha,'bytes':size,'rows':pf.metadata.num_rows},
        'scope':scopes,'candidate_rows':rows,'candidate_count':len(rows),'limit':limit,
        'coverage':'BOUNDED_SOURCE_SAMPLE' if reached_limit else 'ALL_MATCHES_IN_THIS_PARQUET_FILE',
        'whole_month_coverage':False,'validation_errors':['SOURCE_CONTRACT_APPROVAL_REQUIRED','OBSERVATION_LABEL_EVENT_FEATURE_APPROVALS_REQUIRED','FIXED_SPLIT_AND_PROTOCOL_APPROVALS_REQUIRED']}
    raw=canonical_bytes(snapshot);sha=sha_bytes(raw);rel=immutable_copy(root,sha,raw)
    return {'snapshot':snapshot,'snapshot_sha256':sha,'path':str(Path(root)/rel)}


def ingest_approved_source(db,receipt,sha,actor,register_metadata=False):
    """Persist exact reviewed scalar observations and immutable source bindings.

    Labels, incident records, features and dataset memberships have independent
    review flows. This transaction creates none of those objects.
    """
    from decimal import Decimal
    import math
    from zoneinfo import ZoneInfo
    from app.models.domain import StationMetadata,SensorMetadata,ObservationRaw,ObservationStandard
    from app.models.source_observation_binding import SourceObservationBinding
    from app.models.source_contracts import SourceContractPacket
    if not actor.user_id or actor.role not in {'operator','reviewer','admin'}:raise DependencyError('AUTHENTICATED_OPERATOR_REQUIRED')
    db.query(SourceContractPacket).filter_by(contract_id=receipt.get('contract_id')).with_for_update().first()
    authority=source_authority(db,receipt,sha);inserted=existing=0
    for oid,proof in sorted(receipt['observations'].items()):
        if not 1<=len(oid)<=128:raise DependencyError('STANDARD_OBSERVATION_ID_INVALID')
        station_id,sensor_id,var=proof['canonical_station_id'],proof['canonical_sensor_id'],proof['standard_variable']
        station=db.query(StationMetadata).filter_by(station_id=station_id).first()
        sensor=db.query(SensorMetadata).filter_by(sensor_id=sensor_id).first()
        if not station:
            refs=proof.get('field_evidence',{}).get('canonical_station_identity')
            if not register_metadata or not proof.get('canonical_station_name') or not refs:raise DependencyError('APPROVED_STATION_METADATA_REGISTRATION_REQUIRED:'+oid)
            if any(r.get('file_sha256') not in {f['sha256'] for f in receipt['files']} or not r.get('locator') or not r.get('claim') for r in refs):raise DependencyError('CANONICAL_STATION_IDENTITY_EVIDENCE_INVALID')
            station=StationMetadata(station_id=station_id,station_name=proof['canonical_station_name'],status='SOURCE_CONTRACT_APPROVED')
            db.add(station);db.flush()
        if not sensor:
            refs=proof.get('field_evidence',{}).get('canonical_sensor_identity')
            if not register_metadata or not refs:raise DependencyError('APPROVED_SENSOR_METADATA_REGISTRATION_REQUIRED:'+oid)
            if any(r.get('file_sha256') not in {f['sha256'] for f in receipt['files']} or not r.get('locator') or not r.get('claim') for r in refs):raise DependencyError('CANONICAL_SENSOR_IDENTITY_EVIDENCE_INVALID')
            sensor=SensorMetadata(station_id=station_id,sensor_id=sensor_id,variable_code=var,status='SOURCE_CONTRACT_APPROVED')
            db.add(sensor);db.flush()
        if sensor.station_id!=station_id or sensor.variable_code!=var:raise DependencyError('CANONICAL_SENSOR_METADATA_SCOPE_MISMATCH:'+oid)
        stamp=datetime.fromisoformat(proof['timestamp_utc']).astimezone(timezone.utc).replace(tzinfo=None)
        typed=proof['quantity_kind']!='SCALAR'
        rawnum=float(Decimal(str(proof['source_value_raw'])))
        stdnum=None if typed else float(Decimal(str(proof['value'])))
        if not math.isfinite(rawnum) or Decimal(str(rawnum))!=Decimal(str(proof['source_value_raw'])) or (not typed and (not math.isfinite(stdnum) or Decimal(str(stdnum))!=Decimal(str(proof['value'])))):raise DependencyError('ORM_NUMERIC_PRECISION_LOSS:'+oid)
        if any(v is not None and type(v) not in {int,float} for v in proof['depth'].values()):raise DependencyError('ORM_TYPED_DEPTH_TRANSFORM_NOT_APPROVED:'+oid)
        raw=db.query(ObservationRaw).filter_by(station_id=station_id,sensor_id=sensor_id,variable_code=var,timestamp_utc=stamp).first()
        standard=db.get(ObservationStandard,oid);binding=db.get(SourceObservationBinding,oid)
        if standard or raw or binding:
            if not standard or not raw or not binding:raise DependencyError('SOURCE_INGEST_EXISTING_OBSERVATION_UNBOUND:'+oid)
            if (binding.receipt_sha256!=sha or binding.payload!=proof or binding.contract_id!=receipt['contract_id']
                or binding.approval_history_id!=authority['approval_history_id']):raise DependencyError('SOURCE_INGEST_BINDING_CHANGED:'+oid)
            if (standard.station_id!=station_id or standard.sensor_id!=sensor_id or standard.variable_code!=var
                or standard.timestamp_utc!=stamp or standard.value_standard!=stdnum or standard.value_raw!=rawnum
                or raw.source_system!=proof['source_group'] or raw.value_raw!=rawnum or raw.qc_flag!=proof.get('source_qc_raw')
                or raw.mqc_flag!=proof.get('source_mqc_raw') or raw.source_item_code!=proof['source_item_code']):raise DependencyError('SOURCE_INGEST_EXISTING_RECORD_CHANGED:'+oid)
            existing+=1;continue
        if db.query(SourceObservationBinding).filter_by(parquet_sha256=proof['parquet_sha256'],source_row_locator=proof['source_row_locator']).first():raise DependencyError('SOURCE_ROW_ALREADY_INGESTED_WITH_DIFFERENT_ID')
        if db.query(ObservationStandard).filter_by(station_id=station_id,sensor_id=sensor_id,variable_code=var,timestamp_utc=stamp).first():raise DependencyError('STANDARD_NATURAL_KEY_ALREADY_EXISTS')
        received=proof.get('source_receive_timestamp_utc')
        received=datetime.fromisoformat(received).astimezone(timezone.utc).replace(tzinfo=None) if received else None
        common=dict(station_id=station_id,sensor_id=sensor_id,variable_code=var,timestamp_utc=stamp,value_raw=rawnum,
            qc_flag=proof.get('source_qc_raw'),mqc_flag=proof.get('source_mqc_raw'),source_item_code=proof['source_item_code'],
            water_step=proof['depth']['step'],from_depth=proof['depth']['from'],to_depth=proof['depth']['to'],receive_time=received)
        db.add(ObservationRaw(**common,value_unit=proof['source_unit'],source_system=proof['source_group'],
            timestamp_kst=stamp.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Seoul')).replace(tzinfo=None),value_status='SOURCE_CONTRACT_ACCEPTED'))
        db.add(ObservationStandard(**common,observation_id=oid,value_standard=stdnum,source_unit=proof['source_unit'],
            standard_unit=proof['unit'],conversion_rule=json.dumps(proof['quantity_transform']|{'typed_anchor_only':typed},sort_keys=True),
            standardization_version='source-contract-v2:'+receipt['packet_sha256'][:16]))
        db.flush()
        db.add(SourceObservationBinding(observation_id=oid,contract_id=receipt['contract_id'],approval_history_id=authority['approval_history_id'],
            receipt_sha256=sha,source_sha256=proof['source_sha256'],parquet_sha256=proof['parquet_sha256'],source_row_locator=proof['source_row_locator'],
            exact_scope_key=proof['exact_scope_key'],payload=proof,created_by=actor.user_id));db.flush();inserted+=1
    return {'contract_id':receipt['contract_id'],'receipt_sha256':sha,'inserted':inserted,'already_bound':existing,
        'labels_created':0,'events_created':0,'features_created':0,'dataset_memberships_created':0,'requires_independent_downstream_reviews':True}


def reattach_frozen_dependencies(db,base,frozen,root):
    if frozen.get('schema_version')!=SCHEMA:return base
    roles=validate_frozen_shape(frozen,root)
    specs=[]
    for dep in roles:
        path=(Path(root)/dep['path']).resolve()
        if not path.is_relative_to(Path(root).resolve()/'dependencies'):raise DependencyError('FROZEN_DEPENDENCY_PATH_INVALID')
        specs.append({'path':str(path),'sha256':dep['sha256'],'role':dep['role']})
    return freeze_dependencies(db,base,specs,root,[root]) | {'verified_source_roots':frozen['verified_source_roots']}


def validate_frozen_shape(snapshot,root):
    if not isinstance(snapshot,dict) or snapshot.get('schema_version')!=SCHEMA:raise DependencyError('LEGACY_DATASET_SOURCE_CONTRACT_FREEZE_REQUIRED')
    if not isinstance(snapshot.get('source_contract_root'),str) or Path(snapshot['source_contract_root']).resolve()!=Path(root).resolve():raise DependencyError('SNAPSHOT_DEPENDENCY_ROOT_CHANGED')
    if not isinstance(snapshot.get('verified_source_roots'),list) or not snapshot['verified_source_roots'] or any(not isinstance(r,str) for r in snapshot['verified_source_roots']):raise DependencyError('FROZEN_SOURCE_ROOTS_INVALID')
    result=[];seen=set()
    for field in ['source_contracts','frozen_protocol_dependencies','draft_review_dependencies']:
        deps=snapshot.get(field,[])
        if not isinstance(deps,list):raise DependencyError('FROZEN_DEPENDENCY_LIST_INVALID')
        for dep in deps:
            if not isinstance(dep,dict) or dep.get('role') not in ROLES or not isinstance(dep.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',dep['sha256']):raise DependencyError('FROZEN_DEPENDENCY_DESCRIPTOR_INVALID')
            if dep.get('path')!='dependencies/'+dep['sha256']+'.json':raise DependencyError('FROZEN_DEPENDENCY_PATH_INVALID')
            expected='SOURCE_CONTRACT' if field=='source_contracts' else 'REVIEW_CANDIDATES' if field=='draft_review_dependencies' else None
            if (expected and dep['role']!=expected) or (not expected and dep['role'] not in {'SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY'}):raise DependencyError('FROZEN_DEPENDENCY_ROLE_INVALID')
            if dep['sha256'] in seen:raise DependencyError('DUPLICATE_DEPENDENCY')
            if not isinstance(dep.get('review_errors'),list) or (dep.get('approval_receipt') is not None and not isinstance(dep['approval_receipt'],dict)):raise DependencyError('FROZEN_APPROVAL_BINDING_INVALID')
            seen.add(dep['sha256']);result.append(dep)
    return result


def frozen_integrity_errors(db,snapshot,root):
    if not isinstance(snapshot,dict) or snapshot.get('schema_version')!=SCHEMA:return ['LEGACY_DATASET_SOURCE_CONTRACT_FREEZE_REQUIRED']
    errors=[]
    try:deps=validate_frozen_shape(snapshot,root)
    except (ValueError,TypeError) as exc:return [getattr(exc,'code','FROZEN_DEPENDENCY_SHAPE_INVALID')]
    for dep in deps:
        try:
            receipt,_,sha=read_bounded(Path(root)/dep['path'],[root],dep['sha256'])
            authority,issues=dependency_review(db,receipt,sha,dep['role'])
            errors.extend(dep['role']+':'+x for x in issues)
            if authority!=dep.get('approval_receipt'):errors.append('FROZEN_APPROVAL_RECEIPT_CHANGED:'+dep['sha256'])
        except (ValueError,OSError) as exc:errors.append(getattr(exc,'code','FROZEN_DEPENDENCY_READ_FAILED'))
    if not snapshot.get('source_contracts'):errors.append('SOURCE_CONTRACT_DEPENDENCIES_MISSING')
    for role in ['SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY']:
        if sum(x.get('role')==role for x in snapshot.get('frozen_protocol_dependencies',[]))!=1:errors.append(role+'_ONE_FROZEN_DEPENDENCY_REQUIRED')
    try:errors.extend(protocol_binding_errors(snapshot))
    except (ValueError,OSError,KeyError,TypeError) as exc:errors.append(getattr(exc,'code','FROZEN_PROTOCOL_BINDING_INVALID'))
    return sorted(set(errors))
