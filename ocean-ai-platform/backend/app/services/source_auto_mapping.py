"""System-policy approval and resumable ingestion of verified monthly Parquet.

The source contract approves operational mapping, not physical identity, QC,
events, labels or model/dataset eligibility. No human identity is impersonated.
"""
from bisect import bisect_right
from collections import Counter
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import re

import duckdb
import pyarrow.parquet as pq
from sqlalchemy import tuple_, func
from app.core.config import settings
from app.models.domain import (ApprovalHistory, AuditLog, MDCItemMapping,
                               ObservationRaw, ObservationStandard,
                               SensorMetadata, StationMetadata)
from app.models.source_contracts import SourceContractPacket, SourceContractDecision
from app.models.source_observation_binding import SourceObservationBinding
from app.services.observation_mapping import policy, digest, VERSION, mapping
from app.services.source_contract_review import exact_scope_key
from app.services import source_contract_authority as authority

SCHEMA = 'source-operational-mapping-1'
RECEIPT_SCHEMA = 'source-operational-mapping-receipt-1'
SYSTEM_ID = 'system:source-standard-mapping'
SOURCE_PATTERN = re.compile(r'(GD_OBS_BU|GD_OBS_VBU|GR_OBS_ST)_(20\d{2}(?:0[1-9]|1[0-2]))')


def _error(code):
    raise authority.SourceContractError(code)


def _file(root, path, role):
    relative = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    target = authority._path(root, relative)
    before = target.stat()
    sha = hashlib.sha256()
    with target.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            sha.update(chunk)
    after = target.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        _error('SOURCE_CHANGED_DURING_HASH')
    return dict(role=role, path=relative, sha256=sha.hexdigest(), bytes=after.st_size)


def prepare_manifest(path, root=None):
    """File path, manifest, Parquet bytes and row census must agree."""
    root = Path(root or authority.SOURCE_ROOT).resolve()
    path = Path(path).resolve()
    descriptor = _file(root, path, 'SOURCE_MANIFEST')
    match = SOURCE_PATTERN.fullmatch(path.parent.name)
    if path.name != 'manifest.json' or not match:
        _error('AUTO_SOURCE_MANIFEST_PATH_INVALID')
    manifest = authority._json_file(path)
    source, month = match[1], match[2][:4] + '-' + match[2][4:]
    if (manifest.get('status') != 'VERIFIED' or manifest.get('source_system') != source
            or Path(manifest.get('raw_path', '')).resolve() != path.parent / 'raw.parquet'
            or not authority._sha(manifest.get('source_sha256'))
            or not isinstance(manifest.get('source_path'), str)
            or type(manifest.get('source_size')) is not int or manifest['source_size'] <= 0):
        _error('AUTO_SOURCE_MANIFEST_INVALID')
    parquet = _file(root, path.parent / 'raw.parquet', 'PARQUET')
    pf = pq.ParquetFile(root / parquet['path'])
    required = {'OBS_POST_ID', 'OBS_ITEM_CODE', 'OBS_TIME', 'OBS_VALUE'}
    if (parquet['sha256'] != manifest.get('raw_sha256')
            or pf.metadata.num_rows != manifest.get('raw_rows')
            or manifest.get('csv_recount_rows') != manifest.get('raw_rows')
            or not required <= set(pf.schema_arrow.names)):
        _error('AUTO_SOURCE_PARQUET_RECONCILIATION_FAILED')
    if {'FR_DEPTH', 'FROM_DEPTH'} <= set(pf.schema_arrow.names):
        _error('SOURCE_DEPTH_ALIAS_CONFLICT')
    original = Path(manifest['source_path'])
    if original.is_file():
        authority._hash_file(original, manifest['source_sha256'], manifest['source_size'])
        availability = 'RAW_AND_TRANSFORM_VERIFIED'
    else:
        availability = 'VERIFIED_PRESERVED_TRANSFORM_ONLY'
    adopted = policy()
    payload = dict(schema_version=SCHEMA, mapping_policy=adopted,
                   policy_sha256=digest(adopted), source_group=source, month=month,
                   files=[descriptor, parquet], source_sha256=manifest['source_sha256'],
                   original_path=manifest['source_path'], original_bytes=manifest['source_size'],
                   source_availability_policy=availability, parquet_rows=pf.metadata.num_rows,
                   scope='ALL_MATCHING_MAPPED_CHANNELS_IN_VERIFIED_FILE',
                   approval_scope='OPERATIONAL_STANDARDIZATION_ONLY',
                   training_eligible=False, qc_approved=False)
    payload['contract_id'] = 'auto-map-' + digest(payload)
    return payload


def packet_errors(packet, root=None, verify_sources=False):
    errors = []
    if not isinstance(packet, dict) or packet.get('schema_version') != SCHEMA:
        return ['AUTO_SOURCE_SCHEMA_INVALID']
    if packet.get('mapping_policy') != policy() or packet.get('policy_sha256') != digest(policy()):
        errors.append('AUTO_MAPPING_POLICY_CHANGED')
    if (packet.get('training_eligible') is not False or packet.get('qc_approved') is not False
            or packet.get('approval_scope') != 'OPERATIONAL_STANDARDIZATION_ONLY'):
        errors.append('AUTO_APPROVAL_SCOPE_INVALID')
    expected_id = 'auto-map-' + digest({k: v for k, v in packet.items() if k != 'contract_id'})
    if packet.get('contract_id') != expected_id:
        errors.append('AUTO_CONTRACT_ID_MISMATCH')
    files = packet.get('files', [])
    if (not isinstance(files, list) or len(files) != 2
            or any(not isinstance(f, dict) for f in files)
            or {f.get('role') for f in files} != {'PARQUET', 'SOURCE_MANIFEST'}):
        errors.append('AUTO_SOURCE_FILES_INVALID')
    if verify_sources and not errors:
        try:
            root = root or authority.SOURCE_ROOT
            manifest = next(f for f in files if f['role'] == 'SOURCE_MANIFEST')
            rebuilt = prepare_manifest(authority._path(root, manifest['path']), root)
            if rebuilt != packet:
                errors.append('AUTO_SOURCE_PACKET_OR_BYTES_CHANGED')
        except (OSError, ValueError, KeyError, StopIteration):
            errors.append('AUTO_SOURCE_PACKET_OR_BYTES_CHANGED')
    return errors


def approve_manifest(db, packet, root=None):
    if not settings.SOURCE_AUTO_MAPPING_ENABLED or settings.DATA_MODE != 'live':
        _error('SOURCE_AUTO_MAPPING_DISABLED')
    errors = packet_errors(packet, root, verify_sources=True)
    if errors:
        _error(errors[0])
    cid = packet['contract_id']
    # Serialize two CLI workers on the same immutable manifest.
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': int(cid[-15:], 16)})
    existing = db.get(SourceContractPacket, cid)
    if existing:
        decision = db.query(SourceContractDecision).filter_by(contract_id=cid).order_by(SourceContractDecision.approval_history_id.desc()).first()
        if not decision:
            _error('AUTO_SOURCE_DECISION_MISSING')
        verify_receipt(db, decision.receipt, decision.receipt_sha256, root=root)
        return decision.receipt, decision.receipt_sha256
    packet_sha = digest(packet)
    db.add(SourceContractPacket(contract_id=cid, payload=packet, packet_sha256=packet_sha,
                                requested_by=SYSTEM_ID, status='APPROVED'))
    db.flush()
    db.add(ApprovalHistory(approval_type='SOURCE_CONTRACT', target_id=cid, requested_by=SYSTEM_ID,
                           approval_status='PENDING', comment='packet_sha256=' + packet_sha))
    db.flush()
    history = ApprovalHistory(approval_type='SOURCE_CONTRACT', target_id=cid, requested_by=SYSTEM_ID,
                              approved_by=SYSTEM_ID, approval_status='APPROVED')
    db.add(history)
    db.flush()
    receipt = dict(schema_version=RECEIPT_SCHEMA, source_contract_schema=SCHEMA, contract_id=cid,
                   packet_sha256=packet_sha, status='APPROVED', approval_complete=True,
                   approved_by=SYSTEM_ID, requested_by=SYSTEM_ID, approval_mode='SYSTEM_POLICY',
                   approval_scope='OPERATIONAL_STANDARDIZATION_ONLY', training_eligible=False,
                   qc_approved=False, packet=packet,
                   approval_receipt=dict(approval_history_id=history.id, approval_type='SOURCE_CONTRACT',
                                         target_id=cid, reviewer_id=SYSTEM_ID, reviewer_role='system',
                                         decision='APPROVED', decided_at=datetime.now(timezone.utc).isoformat()))
    sha = digest(receipt)
    history.comment = 'snapshot_sha256=' + sha
    db.add(SourceContractDecision(approval_history_id=history.id, contract_id=cid, packet_sha256=packet_sha,
                                 decision='APPROVED', reviewer_id=SYSTEM_ID, reviewer_role='system',
                                 receipt_sha256=sha, receipt=receipt))
    db.add(AuditLog(actor=SYSTEM_ID, action='SOURCE_POLICY_AUTO_APPROVED', resource_type='SOURCE_CONTRACT',
                    resource_id=cid, detail_json=dict(policy_sha256=packet['policy_sha256'],
                                                     human_approval=False, scope=receipt['approval_scope'])))
    db.flush()
    return receipt, sha


def verify_receipt(db, receipt, sha, *, root=None, verify_sources=True):
    if (digest(receipt) != sha or receipt.get('schema_version') != RECEIPT_SCHEMA
            or receipt.get('approval_scope') != 'OPERATIONAL_STANDARDIZATION_ONLY'
            or receipt.get('training_eligible') is not False or receipt.get('qc_approved') is not False):
        _error('AUTO_SOURCE_RECEIPT_INVALID')
    cid = receipt.get('contract_id')
    packet = db.get(SourceContractPacket, cid)
    history = db.query(ApprovalHistory).filter_by(approval_type='SOURCE_CONTRACT', target_id=cid).order_by(ApprovalHistory.id.desc()).first()
    request = db.query(ApprovalHistory).filter_by(approval_type='SOURCE_CONTRACT', target_id=cid, approval_status='PENDING').first()
    row = db.get(SourceContractDecision, receipt.get('approval_receipt', {}).get('approval_history_id'))
    if not packet or not history or not row or not request:
        _error('AUTO_SOURCE_LEDGER_MISSING')
    if packet.status != 'APPROVED' or history.approval_status != 'APPROVED' or row.decision != 'APPROVED':
        _error('AUTO_SOURCE_APPROVAL_REVOKED')
    if (row.receipt != receipt or row.receipt_sha256 != sha or row.contract_id != cid
            or history.id != row.approval_history_id or history.comment != 'snapshot_sha256=' + sha
            or request.id >= history.id or request.approved_by is not None
            or request.comment != 'packet_sha256=' + packet.packet_sha256
            or receipt.get('packet') != packet.payload or digest(packet.payload) != packet.packet_sha256
            or receipt.get('packet_sha256') != packet.packet_sha256 or row.packet_sha256 != packet.packet_sha256):
        _error('AUTO_SOURCE_LEDGER_HASH_MISMATCH')
    actors = [packet.requested_by, request.requested_by, history.requested_by, history.approved_by,
              row.reviewer_id, receipt.get('approved_by'), receipt.get('requested_by'),
              receipt.get('approval_receipt', {}).get('reviewer_id')]
    if any(a != SYSTEM_ID for a in actors) or row.reviewer_role != 'system' or receipt['approval_receipt'].get('reviewer_role') != 'system':
        _error('AUTO_SOURCE_ACTOR_MISMATCH')
    errors = packet_errors(packet.payload, root, verify_sources)
    if errors:
        _error(errors[0])
    return dict(contract_id=cid, approval_history_id=history.id, receipt_sha256=sha,
                approval_scope=receipt['approval_scope'], training_eligible=False)


def adopt_mapping(db):
    for code, spec in policy()['items'].items():
        row = db.query(MDCItemMapping).filter_by(source_item_code=code).first()
        if row is None:
            row = MDCItemMapping(source_item_code=code)
            db.add(row)
        row.standard_variable_code, row.standard_unit = spec['variable'], spec['unit']
        row.sensor_type, row.mapping_version, row.active = spec['sensor_type'], VERSION, True
    db.flush()


def window(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        _error('AUTO_WINDOW_REQUIRES_SOURCE_LOCAL_CLOCK')
    return parsed


def selected_batches(packet, start, end, root=None, batch_size=1000, items=None):
    """Select before Python materialization, retaining physical Parquet locators."""
    root = Path(root or authority.SOURCE_ROOT)
    file = next(f for f in packet['files'] if f['role'] == 'PARQUET')
    path = authority._path(root, file['path'])
    pf = pq.ParquetFile(path)
    cumulative, count = [], 0
    for group in range(pf.num_row_groups):
        cumulative.append(count)
        count += pf.metadata.row_group(group).num_rows
    allowed = sorted(items or packet['mapping_policy']['items'])
    if any(code not in packet['mapping_policy']['items'] for code in allowed):
        _error('AUTO_ITEM_NOT_MAPPED')
    if not 1 <= batch_size <= 2000 or start > end:
        _error('AUTO_INGEST_WINDOW_OR_BATCH_INVALID')
    month_start = datetime.fromisoformat(packet['month'] + '-01')
    month_end = month_start.replace(year=month_start.year+1, month=1) if month_start.month == 12 else month_start.replace(month=month_start.month+1)
    lower, upper = max(start, month_start), min(end, month_end)
    if lower > upper:
        return
    sql = ('SELECT *,file_row_number AS __row_number FROM read_parquet(?,file_row_number=true) '
           'WHERE upper(trim(OBS_ITEM_CODE)) IN (' + ','.join('?' for _ in allowed) + ') '
           'AND try_cast(OBS_TIME AS TIMESTAMP)>=? AND try_cast(OBS_TIME AS TIMESTAMP)<=?')
    with duckdb.connect() as con:
        con.execute('SET threads=2')
        reader = con.execute(sql, [str(path), *allowed, lower, upper]).fetch_record_batch(batch_size)
        for batch in reader:
            rows = batch.to_pylist()
            for row in rows:
                position = row.pop('__row_number')
                row.pop('file_row_number', None)
                group = bisect_right(cumulative, position) - 1
                row['source_row_locator'] = f'parquet_row_group={group};row_index={position-cumulative[group]}'
            yield rows


def source_record(row, packet):
    source, month = packet['source_group'], packet['month']
    station = str(row.get('OBS_POST_ID') or '').strip().upper()
    item = str(row.get('OBS_ITEM_CODE') or '').strip().upper()
    spec = packet['mapping_policy']['items'].get(item)
    if not station or not spec:
        _error('AUTO_SOURCE_IDENTITY_OR_ITEM_INVALID')
    local = window(row['OBS_TIME'])
    if local.strftime('%Y-%m') != month:
        _error('AUTO_SOURCE_CLOCK_MONTH_MISMATCH')
    utc = local.replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(timezone.utc)
    literal = row.get('OBS_VALUE')
    try:
        value = float(literal) if literal is not None and str(literal).strip() else None
    except (ValueError, TypeError):
        _error('AUTO_NONNUMERIC_VALUE')
    if value is not None and not math.isfinite(value):
        _error('AUTO_NONFINITE_VALUE')
    depth = {'step': row.get('WATER_STEP'), 'from': row.get('FR_DEPTH', row.get('FROM_DEPTH')), 'to': row.get('TO_DEPTH')}
    try:
        typed_depth = {k: float(v) if v is not None else None for k, v in depth.items()}
    except (ValueError, TypeError):
        _error('AUTO_DEPTH_INVALID')
    if any(v is not None and not math.isfinite(v) for v in typed_depth.values()):
        _error('AUTO_DEPTH_INVALID')
    sensor = 'L_' + digest([source, station, item, depth])[:48]
    oid = digest([station, sensor, spec['variable'], utc.isoformat()])
    received_raw = row.get('RECEIVE_TIME')
    try:
        received = window(received_raw).replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(timezone.utc) if received_raw else None
    except (ValueError, TypeError):
        _error('AUTO_RECEIVE_CLOCK_INVALID')
    grain = dict(source_group=source, station_code=station, item_code=item, month=month,
                 depth_step=depth['step'], depth_from=depth['from'], depth_to=depth['to'])
    proof = dict(schema_version='source-operational-binding-1', canonical_station_id=station,
                 canonical_sensor_id=sensor, standard_variable=spec['variable'], source_group=source,
                 source_station_code=station, source_item_code=item, source_month=month,
                 source_station_literal=row['OBS_POST_ID'], source_item_literal=row['OBS_ITEM_CODE'],
                 source_time_raw=row['OBS_TIME'], source_value_raw=literal, value=value,
                 timestamp_utc=utc.isoformat(), source_receive_time_raw=received_raw,
                 source_receive_timestamp_utc=received.isoformat() if received else None,
                 source_qc_raw=row.get('QC_FLAG'), source_mqc_raw=row.get('MQC_FLAG'),
                 source_n1_aqc_raw=row.get('N1_AQC_FLAG'), depth=depth, exact_scope_key=exact_scope_key(grain),
                 source_row_locator=row['source_row_locator'], source_sha256=packet['source_sha256'],
                 parquet_sha256=next(f['sha256'] for f in packet['files'] if f['role'] == 'PARQUET'),
                 source_unit=spec['unit'], unit=spec['unit'], quantity_kind=spec['quantity_kind'],
                 timezone='Asia/Seoul', source_clock_semantics='SYSTEM_ADOPTED_OBSERVED_AT',
                 mapping_version=VERSION, policy_sha256=packet['policy_sha256'],
                 physical_sensor_id=None, sensor_episode_id=None, qc_approved=False, training_eligible=False)
    common = dict(station_id=station, sensor_id=sensor, variable_code=spec['variable'],
                  timestamp_utc=utc.replace(tzinfo=None), value_raw=value,
                  qc_flag=proof['source_qc_raw'], mqc_flag=proof['source_mqc_raw'], source_item_code=item,
                  water_step=typed_depth['step'], from_depth=typed_depth['from'], to_depth=typed_depth['to'],
                  receive_time=received.replace(tzinfo=None) if received else None)
    raw = dict(common, timestamp_kst=local, value_unit=spec['unit'], source_system=source,
               value_status='MISSING' if value is None else 'UNREVIEWED')
    standard = dict(common, observation_id=oid, value_standard=value, source_unit=spec['unit'],
                    standard_unit=spec['unit'], conversion_rule='SYSTEM_MDC_IDENTITY;DATUM_UNVERIFIED' if spec['variable'] == 'TIDE' else 'SYSTEM_MDC_IDENTITY',
                    standardization_version=VERSION)
    return raw, standard, proof


def _insert(db, model, rows, keys):
    if not rows:
        return
    dialect = db.get_bind().dialect.name
    if dialect == 'postgresql':
        # One driver bulk call avoids compiling thousands of ORM bind nodes for
        # each of the three observation tables. Values remain driver-escaped.
        from psycopg2.extras import execute_values, Json
        columns = list(rows[0])
        if any(set(row) != set(columns) for row in rows) or any(k not in model.__table__.columns for k in columns+keys):
            _error('AUTO_BULK_COLUMNS_INVALID')
        def adapt(value):
            return Json(value, dumps=lambda x:json.dumps(x,ensure_ascii=False,allow_nan=False)) if isinstance(value,dict) else value
        if model is SourceObservationBinding and any(row['bound_at_utc'].tzinfo is None for row in rows):
            _error('BINDING_CLOCK_EXPLICIT_OFFSET_REQUIRED')
        sql = ('INSERT INTO "'+model.__tablename__+'" ('+','.join('"'+c+'"' for c in columns)+') VALUES %s '
               'ON CONFLICT ('+','.join('"'+k+'"' for k in keys)+') DO NOTHING')
        connection = db.connection().connection.dbapi_connection
        with connection.cursor() as cursor:
            execute_values(cursor,sql,[tuple(adapt(row[c]) for c in columns) for row in rows],page_size=2000)
        return
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        _error('AUTO_INGEST_DIALECT_UNSUPPORTED')
    db.execute(insert(model).values(rows).on_conflict_do_nothing(index_elements=keys))


def _verify_rows(packet, rows, root, cache):
    file = next(f for f in packet['files'] if f['role'] == 'PARQUET')
    path = authority._path(root, file['path'])
    stat = path.stat()
    signature = (str(path), stat.st_size, stat.st_mtime_ns, file['sha256'])
    if cache.get('verified_file') != signature:
        authority._hash_file(path, file['sha256'], file['bytes'])
        cache.clear()
        cache['verified_file'] = signature
        cache['groups'] = OrderedDict()
    pf = pq.ParquetFile(path)
    groups = cache['groups']
    for row in rows:
        match = re.fullmatch(r'parquet_row_group=(0|[1-9]\d*);row_index=(0|[1-9]\d*)', str(row.get('source_row_locator', '')))
        if not match:
            _error('AUTO_SOURCE_LOCATOR_INVALID')
        group, index = map(int, match.groups())
        if group >= pf.num_row_groups or index >= pf.metadata.row_group(group).num_rows:
            _error('AUTO_SOURCE_LOCATOR_OUT_OF_RANGE')
        if group not in groups:
            groups[group] = pf.read_row_group(group)
            while len(groups) > 2:
                groups.popitem(last=False)
        actual = groups[group].slice(index, 1).to_pylist()[0]
        if actual != {k:v for k,v in row.items() if k != 'source_row_locator'}:
            _error('AUTO_SOURCE_LITERAL_MISMATCH')


def ingest_batch(db, receipt, sha, rows, root=None, source_cache=None, *, register_source_identifiers=False):
    if not settings.SOURCE_AUTO_MAPPING_ENABLED or settings.DATA_MODE != 'live':
        _error('SOURCE_AUTO_MAPPING_DISABLED')
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': int(receipt['contract_id'][-15:],16)})
    verify_receipt(db, receipt, sha, root=root, verify_sources=False)
    packet = receipt['packet']
    _verify_rows(packet, rows, root or authority.SOURCE_ROOT, {} if source_cache is None else source_cache)
    counts, prepared = Counter(selected_rows=len(rows)), {}
    stations = {s[0] for s in db.query(StationMetadata.station_id).all()}
    for row in rows:
        try:
            raw, std, proof = source_record(row, packet)
            if raw['station_id'] not in stations:
                if not register_source_identifiers:
                    _error('AUTO_STATION_NOT_REGISTERED')
                # This is the exact source identifier, not a facility identity
                # decision: do not invent a name, position or installation date.
                db.add(StationMetadata(station_id=raw['station_id'], station_name=raw['station_id'],
                                       status='SOURCE_IDENTIFIER_ONLY'))
                db.add(AuditLog(actor=SYSTEM_ID, action='SOURCE_STATION_IDENTIFIER_REGISTERED',
                                resource_type='STATION_REFERENCE', resource_id=raw['station_id'],
                                detail_json=dict(contract_id=receipt['contract_id'], source_group=packet['source_group'],
                                                 parquet_sha256=proof['parquet_sha256'],
                                                 source_row_locator=proof['source_row_locator'],
                                                 physical_identity_approved=False)))
                stations.add(raw['station_id'])
                counts['registered_source_identifiers'] += 1
            oid = std['observation_id']
            if oid in prepared:
                if {k:v for k,v in prepared[oid][2].items() if k != 'source_row_locator'} != {k:v for k,v in proof.items() if k != 'source_row_locator'}:
                    _error('AUTO_DUPLICATE_NATURAL_KEY_CONFLICT')
                counts['duplicate_source_rows'] += 1
                continue
            prepared[oid] = (raw, std, proof)
        except (authority.SourceContractError, ValueError, TypeError) as exc:
            counts['quarantined_rows'] += 1
            counts['reason:' + (getattr(exc, 'code', None) or 'AUTO_ROW_INVALID')] += 1
    ids = list(prepared)
    previous = {b.observation_id: b for b in db.query(SourceObservationBinding).filter(SourceObservationBinding.observation_id.in_(ids)).all()} if ids else {}
    fresh = []
    for oid, row in prepared.items():
        binding = previous.get(oid)
        if binding:
            if binding.receipt_sha256 != sha or binding.contract_id != receipt['contract_id']:
                _error('AUTO_EXISTING_BINDING_POLICY_CONFLICT')
            if (binding.approval_history_id != receipt['approval_receipt']['approval_history_id']
                    or binding.created_by != SYSTEM_ID or binding.bound_at_utc is None
                    or any(getattr(binding,k) != binding.payload.get(k) for k in
                           ('source_sha256','parquet_sha256','source_row_locator','exact_scope_key'))):
                _error('AUTO_EXISTING_BINDING_CONTENT_CONFLICT')
            old, new = ({k:v for k,v in p.items() if k != 'source_row_locator'} for p in (binding.payload, row[2]))
            if old != new:
                counts['quarantined_rows'] += 1
                counts['reason:AUTO_DUPLICATE_NATURAL_KEY_CONFLICT'] += 1
                continue
            counts['already_bound_rows'] += 1
            if binding.source_row_locator != row[2]['source_row_locator']:
                counts['duplicate_source_rows'] += 1
        else:
            fresh.append(row)
    sensors = {raw['sensor_id']: (raw, proof) for raw, _, proof in fresh}
    existing = {s.sensor_id:s for s in db.query(SensorMetadata).filter(SensorMetadata.sensor_id.in_(sensors)).all()} if sensors else {}
    for sid, (raw, proof) in sensors.items():
        sensor = existing.get(sid)
        if sensor and (sensor.station_id != raw['station_id'] or sensor.variable_code != raw['variable_code']):
            _error('AUTO_LOGICAL_SENSOR_SCOPE_CONFLICT')
        if not sensor:
            db.add(SensorMetadata(sensor_id=sid, station_id=raw['station_id'], variable_code=raw['variable_code'],
                                  sensor_type=mapping(proof['source_item_code'])['sensor_type'], status='LOGICAL_SOURCE_CHANNEL'))
    db.flush()
    natural = ['station_id', 'sensor_id', 'variable_code', 'timestamp_utc']
    _insert(db, ObservationRaw, [r for r, _, _ in fresh], natural)
    _insert(db, ObservationStandard, [s for _, s, _ in fresh], natural)
    # Verify all natural-key records before binding: never bless a preexisting
    # unbound record whose numeric value, unit or source has changed.
    checked = [row for oid,row in prepared.items() if oid not in previous or
               {k:v for k,v in previous[oid].payload.items() if k != 'source_row_locator'} == {k:v for k,v in row[2].items() if k != 'source_row_locator'}]
    checked_ids = [s['observation_id'] for _,s,_ in checked]
    saved = {s.observation_id:s for s in db.query(ObservationStandard).filter(ObservationStandard.observation_id.in_(checked_ids)).all()} if checked_ids else {}
    keys = [tuple(raw[k] for k in natural) for raw, _, _ in checked]
    raw_saved = {tuple(getattr(r,k) for k in natural):r for r in db.query(ObservationRaw).filter(tuple_(*(getattr(ObservationRaw,k) for k in natural)).in_(keys)).all()} if keys else {}
    for raw, standard, _ in checked:
        stored = saved.get(standard['observation_id'])
        original = raw_saved.get(tuple(raw[k] for k in natural))
        if (not stored or not original or any(getattr(stored,k) != v for k,v in standard.items())
                or any(getattr(original,k) != v for k,v in raw.items())):
            _error('AUTO_EXISTING_OBSERVATION_CONTENT_CONFLICT')
    now = datetime.now(timezone.utc)
    bindings = [dict(observation_id=std['observation_id'], contract_id=receipt['contract_id'],
                     approval_history_id=receipt['approval_receipt']['approval_history_id'], receipt_sha256=sha,
                     source_sha256=proof['source_sha256'], parquet_sha256=proof['parquet_sha256'],
                     source_row_locator=proof['source_row_locator'], exact_scope_key=proof['exact_scope_key'],
                     payload=proof, created_by=SYSTEM_ID, bound_at_utc=now) for _,std,proof in fresh]
    _insert(db, SourceObservationBinding, bindings, ['observation_id'])
    counts['inserted_rows'] += len(fresh)
    counts['missing_value_rows'] += sum(r['value_raw'] is None for r,_,_ in fresh)
    return dict(counts)


def summary(db):
    rows = db.query(ObservationStandard.variable_code, func.count()).join(SourceObservationBinding,
            SourceObservationBinding.observation_id == ObservationStandard.observation_id).group_by(ObservationStandard.variable_code).all()
    auto = db.query(SourceContractPacket).filter(SourceContractPacket.requested_by == SYSTEM_ID)
    span = db.query(func.min(ObservationStandard.timestamp_utc), func.max(ObservationStandard.timestamp_utc)).join(
        SourceObservationBinding, SourceObservationBinding.observation_id == ObservationStandard.observation_id).first()
    return dict(schema_version='source-auto-mapping-status-1', enabled=settings.SOURCE_AUTO_MAPPING_ENABLED,
                mapping_version=VERSION, policy_sha256=digest(policy()), approval_mode='SYSTEM_POLICY',
                auto_approved_contracts=auto.filter(SourceContractPacket.status == 'APPROVED').count(),
                registered_bindings=db.query(SourceObservationBinding).count(),
                mapped_items=[dict(source_item_code=k, **v) for k,v in sorted(policy()['items'].items())],
                variables=[dict(variable_code=v, rows=n) for v,n in rows],
                first_timestamp_utc=span[0].isoformat()+'Z' if span[0] else None,
                last_timestamp_utc=span[1].isoformat()+'Z' if span[1] else None,
                training_approval_created=False, final_qc_approval_created=False)
