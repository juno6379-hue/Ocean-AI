"""Source contracts remain drafts until an authenticated reviewer decides.

There are no implicit identities and no filesystem approval side effects. The
DB transaction stores the exact receipt and ledger hash together; consumers
must verify the latest decision against both immutable payloads. Agent review
and a guide's general convention never grant operational source approval.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from collections import OrderedDict
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from app.models.domain import ApprovalHistory
from app.models.source_contracts import SourceContractPacket, SourceContractDecision
from app.services.source_contract_review import exact_scope_key, GRAIN

SOURCE_ROOT = Path(r'D:\AI_Observation')
SCHEMA = 'source_contract_v2'
EXPORT_SCHEMA = 'source-semantics-identity-period-event-1'
MAX_BYTES = 8 * 1024 * 1024
MAX_OBSERVATIONS = 5000
SHA = re.compile(r'[0-9a-f]{64}')
CONTRACT_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')
FILE_ROLES = {'RAW', 'PARQUET', 'QC_CODEBOOK', 'SOURCE_MANIFEST', 'DOCUMENT', 'SCHEMA', 'SENSOR_METADATA', 'SOURCE_TRANSFORM'}
TYPED_FIELDS = {'CIRCULAR_DEGREES': ('value', 'magnitude'), 'SIGNED_RADIAL': ('value',),
    'VECTOR_UV': ('u', 'v'), 'PROFILE_BINS': ('bin_ids', 'depths', 'values'),
    'TRAJECTORY': ('longitude', 'latitude')}
TYPED_METADATA = {'CIRCULAR_DEGREES': ('magnitude_unit',),
    'SIGNED_RADIAL': ('coordinate_frame', 'site_geometry_version', 'coverage_fraction', 'qc_eligible'),
    'VECTOR_UV': ('coordinate_frame', 'grid_cell_id', 'geometry_version'),
    'PROFILE_BINS': ('coordinate_frame', 'layout_version', 'target_variable', 'unit', 'value_representation'),
    'TRAJECTORY': ('coordinate_frame', 'trajectory_id')}
REQUIRED_STRINGS = ('physical_sensor_id', 'sensor_episode_id', 'source_group', 'source_item_code',
    'source_station_code', 'source_station_literal', 'source_item_literal', 'source_month', 'source_row_locator', 'timezone', 'source_clock_semantics',
    'qc_rule_version', 'event_id', 'canonical_station_id', 'canonical_sensor_id', 'standard_variable',
    'source_unit', 'unit', 'quantity_kind', 'observation_role', 'source_receive_clock_policy')
REQUIRED_EVIDENCE = ('source_group', 'source_item_code', 'standard_variable', 'physical_sensor_id',
    'sensor_episode_id', 'effective_interval', 'source_unit', 'quantity_transform', 'timezone',
    'source_clock_semantics', 'qc_codebook', 'qc_rule_version', 'qc_effective_interval',
    'quantity_kind', 'observation_role', 'available_at', 'qc_available_at', 'source_identifier_transform', 'source_receive_clock_policy')
COMPONENT_REQUIRED_STRINGS = ('physical_sensor_id','sensor_episode_id','event_id','timezone',
    'source_clock_semantics','qc_rule_version','source_receive_clock_policy')
COMPONENT_REQUIRED_EVIDENCE = ('physical_sensor_id','sensor_episode_id','event_id','effective_interval',
    'source_unit','quantity_transform','timezone','source_clock_semantics','qc_codebook','qc_rule_version',
    'qc_effective_interval','qc_decision','available_at','qc_available_at','source_receive_clock_policy',
    'source_identifier_transform')


class SourceContractError(ValueError):
    def __init__(self, code, detail=''):
        self.code, self.detail = code, detail
        super().__init__(code + (':' + detail if detail else ''))


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf8')


def receipt_sha256(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _clock(value):
    if not isinstance(value, str):
        raise ValueError('EXPLICIT_OFFSET_REQUIRED')
    value = datetime.fromisoformat(value)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('EXPLICIT_OFFSET_REQUIRED')
    return value.astimezone(timezone.utc)


def _local_clock(value, timezone_name):
    """Only unambiguous local timestamps; no implicit DST fold selection."""
    raw = datetime.fromisoformat(value)
    if raw.tzinfo is not None:
        raise SourceContractError('SOURCE_CLOCK_FORMAT_UNSUPPORTED')
    zone = ZoneInfo(timezone_name)
    candidates = {raw.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc)
        for fold in (0,1)
        if raw.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)==raw}
    if not candidates:
        raise SourceContractError('SOURCE_CLOCK_NONEXISTENT')
    if len(candidates)!=1:
        raise SourceContractError('SOURCE_CLOCK_AMBIGUOUS')
    return next(iter(candidates))


def _number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('FINITE_DECIMAL_REQUIRED')
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError('FINITE_DECIMAL_REQUIRED')
    return value


def _receive_utc(proof):
    """Explicit receive column clock; no inherited or discarded receive time."""
    if 'source_receive_time_raw' not in proof or 'source_receive_timestamp_utc' not in proof:
        raise SourceContractError('SOURCE_RECEIVE_FIELDS_REQUIRED')
    raw,utc,policy=proof['source_receive_time_raw'],proof['source_receive_timestamp_utc'],proof.get('source_receive_clock_policy')
    if raw is None or raw=='':
        if policy!='ABSENT_IN_SOURCE' or utc is not None:
            raise SourceContractError('SOURCE_RECEIVE_POLICY_MISMATCH')
        result=None
    else:
        if not isinstance(raw,str):
            raise SourceContractError('SOURCE_RECEIVE_LITERAL_TYPE_INVALID')
        if policy=='LOCAL_OBSERVED_TIMEZONE':
            zone=proof['timezone']
        elif policy=='LOCAL_RECEIVE_TIMEZONE' and isinstance(proof.get('source_receive_timezone'),str) and proof['source_receive_timezone']:
            zone=proof['source_receive_timezone']
        else:
            raise SourceContractError('SOURCE_RECEIVE_POLICY_MISMATCH')
        result=_local_clock(raw,zone)
        if result!=_clock(utc):
            raise SourceContractError('SOURCE_RECEIVE_CLOCK_CONVERSION_MISMATCH')
    if 'source_receive_time_literal' in proof and (type(proof['source_receive_time_literal']) is not type(raw) or proof['source_receive_time_literal']!=raw):
        raise SourceContractError('SOURCE_RECEIVE_ALIAS_CONFLICT')
    if 'receive_time_utc' in proof and ((proof['receive_time_utc'] is None) != (result is None)
            or result is not None and _clock(proof['receive_time_utc'])!=result):
        raise SourceContractError('SOURCE_RECEIVE_ALIAS_CONFLICT')
    return result


def _path(root, value):
    if not isinstance(value, str) or '\\' in value or not value:
        raise SourceContractError('NONCANONICAL_SOURCE_PATH')
    rel = PurePosixPath(value)
    if rel.is_absolute() or any(x in {'.', '..', ''} for x in value.split('/')) or ':' in value:
        raise SourceContractError('SOURCE_PATH_OUTSIDE_ROOT')
    root = Path(root)
    target = root.joinpath(*rel.parts)
    # A resolved junction must not turn an untrusted source into a trusted root.
    for part in (root, *root.parents, *target.parents, target):
        if part.exists() and (part.is_symlink() or getattr(part.stat(), 'st_file_attributes', 0) & 0x400):
            raise SourceContractError('SOURCE_REPARSE_PATH')
    if not target.resolve().is_relative_to(root.resolve()):
        raise SourceContractError('SOURCE_PATH_OUTSIDE_ROOT')
    return target


def _hash_file(path, expected, size):
    before = path.stat()
    if not path.is_file() or before.st_size != size:
        raise SourceContractError('SOURCE_FILE_SIZE_MISMATCH', str(path))
    sha = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            sha.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or sha.hexdigest() != expected:
        raise SourceContractError('SOURCE_FILE_HASH_MISMATCH', str(path))


def _json_file(path):
    if path.stat().st_size > 1024 * 1024:
        raise SourceContractError('SOURCE_JSON_TOO_LARGE')
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise SourceContractError('DUPLICATE_SOURCE_JSON_KEY')
            value[key] = item
        return value
    result = json.loads(path.read_text(encoding='utf8'), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(SourceContractError('NONFINITE_SOURCE_JSON')))
    if not isinstance(result, dict):
        raise SourceContractError('SOURCE_JSON_OBJECT_REQUIRED')
    return result


def packet_errors(packet, root=None, verify_sources=False):
    """Return exact readiness failures; nulls are valid in a pending packet."""
    errors = []
    if not isinstance(packet, dict) or packet.get('schema_version') != SCHEMA:
        return ['SOURCE_CONTRACT_SCHEMA_INVALID']
    try:
        if len(canonical_bytes(packet)) > MAX_BYTES:
            return ['SOURCE_CONTRACT_PACKET_TOO_LARGE']
    except (ValueError, TypeError):
        return ['SOURCE_CONTRACT_JSON_INVALID']
    if not CONTRACT_ID.fullmatch(str(packet.get('contract_id', ''))):
        errors.append('CONTRACT_ID_INVALID')
    if any(k in packet for k in ('approved_by', 'approval_receipt', 'approval_complete', 'status')):
        errors.append('CALLER_APPROVAL_FIELDS_FORBIDDEN')
    agent_review = packet.get('agent_review')
    if not isinstance(agent_review, dict) or agent_review.get('approved') is not False:
        errors.append('AGENT_REVIEW_MUST_NOT_APPROVE')
    if packet.get('validation_errors') != []:
        errors.append('UNRESOLVED_PACKET_VALIDATION_ERRORS')
    policy = packet.get('source_availability_policy')
    if not isinstance(policy, str) or policy not in {'RAW_AND_TRANSFORM_REQUIRED', 'APPROVED_TRANSFORM_ONLY'}:
        errors.append('SOURCE_AVAILABILITY_POLICY_UNDECIDED')
    scope = packet.get('scope')
    scope_keys = []
    if not isinstance(scope, list) or not scope:
        errors.append('EXACT_SOURCE_SCOPE_EMPTY')
    else:
        for row in scope:
            if (not isinstance(row, dict) or set(row) != set(GRAIN)
                    or any(not isinstance(row.get(k), str) or not row[k] for k in ('source_group', 'station_code', 'item_code'))
                    or any(row.get(k) is not None and type(row[k]) not in {str, int, float} for k in ('depth_step','depth_from','depth_to'))
                    or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', str(row.get('month', '')))):
                errors.append('EXACT_SOURCE_SCOPE_INVALID')
            else:
                scope_keys.append(exact_scope_key(row))
        if len(set(scope_keys)) != len(scope_keys):
            errors.append('EXACT_SOURCE_SCOPE_DUPLICATE')
    files = packet.get('files')
    files_by_sha, paths = {}, set()
    root = root or SOURCE_ROOT
    if not isinstance(files, list) or not files:
        errors.append('SOURCE_FILES_EMPTY')
        files = []
    for file in files:
        try:
            if not isinstance(file, dict) or not isinstance(file.get('role'), str) or file.get('role') not in FILE_ROLES or not _sha(file.get('sha256')):
                raise SourceContractError('SOURCE_FILE_DESCRIPTOR_INVALID')
            if type(file.get('bytes')) is not int or file['bytes'] < 0:
                raise SourceContractError('SOURCE_FILE_BYTES_INVALID')
            if file['sha256'] in files_by_sha:
                raise SourceContractError('DUPLICATE_SOURCE_FILE_HASH')
            deleted = file.get('availability') == 'ORIGINAL_DELETED'
            if deleted:
                if (file['role'] != 'RAW' or file.get('path') is not None
                        or policy != 'APPROVED_TRANSFORM_ONLY' or not file.get('original_path')):
                    raise SourceContractError('RAW_DELETION_POLICY_NOT_EXPLICIT')
            else:
                path = _path(root, file.get('path'))
                if file['path'] in paths:
                    raise SourceContractError('DUPLICATE_SOURCE_FILE_PATH')
                paths.add(file['path'])
                if verify_sources:
                    _hash_file(path, file['sha256'], file['bytes'])
            files_by_sha[file['sha256']] = file
        except (OSError, SourceContractError) as exc:
            errors.append(str(exc))
    roles = {f.get('role') for f in files if isinstance(f, dict) and isinstance(f.get('role'), str)}
    if not {'RAW', 'PARQUET', 'QC_CODEBOOK', 'SOURCE_MANIFEST'} <= roles:
        errors.append('SOURCE_LINEAGE_ROLES_INCOMPLETE')
    observations = packet.get('observations')
    row_cache = OrderedDict()
    observed_keys = set()
    if not isinstance(observations, dict) or not observations:
        errors.append('OBSERVATION_PROOFS_EMPTY')
        observations = {}
    if len(observations) > MAX_OBSERVATIONS:
        errors.append('OBSERVATION_PROOFS_CAPACITY_EXCEEDED')
    for oid, proof in observations.items():
        local = []
        if not isinstance(oid, str) or not oid or not isinstance(proof, dict):
            errors.append('OBSERVATION_PROOF_INVALID')
            continue
        for field in REQUIRED_STRINGS:
            if not isinstance(proof.get(field), str) or not proof[field].strip():
                local.append('MISSING_' + field.upper())
        if proof.get('validation_errors') != []:
            local.append('UNRESOLVED_PROOF_ERRORS')
        if proof.get('source_clock_semantics') != 'OBSERVED_AT' or proof.get('observation_role') != 'OBSERVED':
            local.append('SOURCE_OBSERVED_ROLE_UNCONFIRMED')
        if proof.get('training_value_status') != 'ACCEPTED':
            local.append('TRAINING_VALUE_NOT_REVIEWED')
        kind = proof.get('quantity_kind')
        transform_ids = proof.get('source_identifier_transform')
        if (not isinstance(transform_ids, dict) or set(transform_ids) != {'station', 'item'}
                or any(not isinstance(transform_ids[k], str) or transform_ids[k] not in {'IDENTITY', 'STRIP_SQLPLUS_PADDING'} for k in transform_ids)):
            local.append('SOURCE_IDENTIFIER_TRANSFORM_UNDEFINED')
        if kind != 'SCALAR':
            bindings, payload = proof.get('typed_payload_bindings'), proof.get('typed_payload')
            if not isinstance(kind, str) or kind not in TYPED_FIELDS:
                local.append('SOURCE_QUANTITY_KIND_UNDEFINED')
            elif not isinstance(bindings, dict) or not isinstance(payload, dict):
                local.append('CURRENT_SOURCE_TYPED_BINDING_MISSING')
            elif (bindings.get('representation') != kind or payload.get('representation') != kind
                    or not isinstance(bindings.get('fields'), dict) or set(bindings['fields']) != set(TYPED_FIELDS[kind])):
                local.append('SOURCE_TYPED_BINDING_FIELDS_INVALID')
            else:
                for field in TYPED_FIELDS[kind]:
                    entries = bindings['fields'][field]
                    if not isinstance(entries, list):
                        entries = [entries]
                    for entry in entries:
                        if (not isinstance(entry, dict) or not isinstance(entry.get('depth'), dict)
                                or set(entry['depth']) != {'step','from','to'}
                                or any(v is not None and type(v) not in {str,int,float} for v in entry['depth'].values())):
                            local.append('SOURCE_TYPED_BINDING_SCOPE_MISSING')
                            continue
                        if (not _sha(entry.get('file_sha256')) or not _sha(entry.get('source_sha256'))
                                or not _sha(entry.get('source_manifest_sha256'))
                                or type(entry.get('row_group')) is not int or type(entry.get('row_index')) is not int
                                or entry['row_group'] < 0 or entry['row_index'] < 0
                                or any(not isinstance(entry.get(f),str) or not entry[f] for f in ('column','source_group','source_station_code','source_item_code','source_station_literal','source_item_literal','source_time_raw'))):
                            local.append('SOURCE_TYPED_COMPONENT_LINEAGE_MISSING')
                        local.extend(component_review_errors(entry,proof,files_by_sha))
                        bound_key = exact_scope_key(dict(source_group=entry.get('source_group'),
                            station_code=entry.get('source_station_code'), item_code=entry.get('source_item_code'),
                            month=proof.get('source_month'), depth_step=entry['depth'].get('step'),
                            depth_from=entry['depth'].get('from'), depth_to=entry['depth'].get('to')))
                        if entry.get('exact_scope_key') != bound_key or bound_key not in scope_keys:
                            local.append('SOURCE_TYPED_BINDING_SCOPE_MISMATCH')
                        observed_keys.add(bound_key)
                metadata = bindings.get('constant_metadata', {})
                if not isinstance(metadata, dict):
                    metadata = {}
                for field in TYPED_METADATA[kind]:
                    if field not in payload or metadata.get(field) != payload[field]:
                        local.append('SOURCE_TYPED_METADATA_NOT_FROZEN_' + field.upper())
                local.extend(typed_depth_pairing_errors(proof))
        depth = proof.get('depth')
        if not isinstance(depth, dict) or set(depth) != {'step', 'from', 'to'} or any(v is not None and type(v) not in {str,int,float} for v in depth.values()):
            local.append('TYPED_DEPTH_REQUIRED')
        else:
            key = exact_scope_key(dict(source_group=proof.get('source_group'), station_code=proof.get('source_station_code'),
                item_code=proof.get('source_item_code'), month=proof.get('source_month'),
                depth_step=depth['step'], depth_from=depth['from'], depth_to=depth['to']))
            if proof.get('exact_scope_key') != key or key not in scope_keys:
                local.append('EXACT_SOURCE_SCOPE_KEY_MISMATCH')
            observed_keys.add(key)
        for field, role in (('source_sha256', 'RAW'), ('parquet_sha256', 'PARQUET'),
                ('source_qc_codebook_sha256', 'QC_CODEBOOK'), ('source_manifest_sha256', 'SOURCE_MANIFEST')):
            if not _sha(proof.get(field)) or files_by_sha.get(proof.get(field), {}).get('role') != role:
                local.append('UNBOUND_' + field.upper())
        evidence = proof.get('field_evidence', {})
        required_evidence = REQUIRED_EVIDENCE + (('typed_payload',) if kind != 'SCALAR' else ()) + (('source_column_map',) if 'source_column_map' in proof else ()) + (('source_receive_timezone',) if proof.get('source_receive_clock_policy')=='LOCAL_RECEIVE_TIMEZONE' else ())
        if 'source_column_map' in proof and (not isinstance(proof['source_column_map'],dict)
                or set(proof['source_column_map']) != {'depth_from'}
                or not isinstance(proof['source_column_map'].get('depth_from'),str)
                or proof['source_column_map']['depth_from'] not in {'FR_DEPTH','FROM_DEPTH'}):
            local.append('SOURCE_COLUMN_MAP_INVALID')
        for field in required_evidence:
            refs = evidence.get(field) if isinstance(evidence, dict) else None
            if not isinstance(refs, list) or not refs or any(not isinstance(r, dict)
                    or not _sha(r.get('file_sha256')) or r['file_sha256'] not in files_by_sha
                    or not isinstance(r.get('locator'), str) or not r['locator']
                    or not isinstance(r.get('claim'), str) or not r['claim'] for r in refs):
                local.append('FIELD_EVIDENCE_MISSING_' + field.upper())
        try:
            zone = ZoneInfo(proof['timezone'])
            stamp = _clock(proof['timestamp_utc'])
            if stamp.astimezone(zone).strftime('%Y-%m') != proof['source_month']:
                local.append('SOURCE_MONTH_TIMEZONE_MISMATCH')
            for first, last in (('effective_start', 'effective_end'), ('qc_effective_start', 'qc_effective_end')):
                if not _clock(proof[first]) <= stamp < _clock(proof[last]):
                    local.append('SOURCE_OR_QC_PERIOD_MISMATCH')
            if _clock(proof['available_at']) < stamp or _clock(proof['qc_available_at']) < stamp:
                local.append('AVAILABILITY_BEFORE_OBSERVATION')
            received=_receive_utc(proof)
            if received is not None and received>_clock(proof['available_at']):
                local.append('SOURCE_AVAILABLE_BEFORE_RECEIVED')
            transform = proof['quantity_transform']
            scale, offset = _number(transform['scale']), _number(transform['offset'])
            if scale == 0 or not isinstance(transform.get('datum'), dict) or not isinstance(transform['datum'].get('kind'), str) or transform['datum'].get('kind') not in {'NOT_APPLICABLE', 'SOURCE_DATUM', 'CONVERSION'}:
                local.append('QUANTITY_TRANSFORM_INVALID')
            if 'TIDE' in str(proof['standard_variable']).upper() and transform['datum'].get('kind') == 'NOT_APPLICABLE':
                local.append('TIDE_DATUM_UNRESOLVED')
            datum = transform['datum']
            if datum.get('kind') == 'SOURCE_DATUM' and (not isinstance(datum.get('identifier'),str) or not datum['identifier']):
                local.append('SOURCE_DATUM_IDENTIFIER_MISSING')
            if datum.get('kind') == 'CONVERSION' and any(not isinstance(datum.get(f),str) or not datum[f] for f in ('source_identifier','target_identifier','version')):
                local.append('DATUM_CONVERSION_REFERENCE_MISSING')
            if verify_sources and not local:
                verify_source_row(proof, files_by_sha, root, row_cache=row_cache)
        except (KeyError, TypeError, ValueError, InvalidOperation, ZoneInfoNotFoundError, OSError) as exc:
            local.append(str(exc) if isinstance(exc, SourceContractError) else 'OBSERVATION_CLOCK_TRANSFORM_INCOMPLETE')
        errors.extend(oid + ':' + item for item in local)
    if set(scope_keys) != observed_keys:
        errors.append('EXACT_SCOPE_OBSERVATION_COVERAGE_INCOMPLETE')
    errors.extend(row_reuse_errors(packet, files_by_sha))
    return sorted(set(errors))


def row_reuse_errors(packet, files_by_sha):
    policy = packet.get('source_row_reuse_policy')
    if not isinstance(policy, dict) or not isinstance(policy.get('policy'),str) or policy.get('policy') not in {'FORBIDDEN', 'EXPLICIT_COMPONENT_SHARING'}:
        return ['SOURCE_ROW_REUSE_POLICY_UNDECIDED']
    claims = {}
    observations = packet.get('observations')
    if not isinstance(observations,dict):
        return ['OBSERVATION_PROOFS_EMPTY']
    for oid, proof in observations.items():
        if not isinstance(proof, dict):
            continue
        sha = proof.get('parquet_sha256')
        match = re.fullmatch(r'parquet_row_group=(0|[1-9]\d*);row_index=(0|[1-9]\d*)', str(proof.get('source_row_locator','')))
        if _sha(sha) and match:
            manifest = files_by_sha.get(proof.get('source_manifest_sha256'), {}) if _sha(proof.get('source_manifest_sha256')) else {}
            column = 'value_raw' if manifest.get('format') == 'MONTHLY_SQLPLUS_RAW_V1' else 'OBS_VALUE'
            claims.setdefault((sha, *map(int,match.groups()), column), set()).add((oid, '__ANCHOR__'))
        bindings = proof.get('typed_payload_bindings')
        fields = bindings.get('fields') if isinstance(bindings, dict) else None
        if not isinstance(fields, dict):
            continue
        for field, entries in fields.items():
            for n, bound in enumerate(entries if isinstance(entries, list) else [entries]):
                if not isinstance(bound, dict) or not _sha(bound.get('file_sha256')) or not isinstance(bound.get('column'),str):
                    continue
                if type(bound.get('row_group')) is not int or type(bound.get('row_index')) is not int:
                    continue
                token = (bound['file_sha256'],bound['row_group'],bound['row_index'],bound['column'])
                claims.setdefault(token, set()).add((oid, str(field)+'['+str(n)+']'))
    errors, allowed = [], {}
    if policy['policy'] == 'EXPLICIT_COMPONENT_SHARING':
        shares = policy.get('reviewed_shared_components')
        if not isinstance(shares, list):
            return ['SOURCE_ROW_SHARING_REVIEW_INCOMPLETE']
        for item in shares:
            if (not isinstance(item,dict) or not _sha(item.get('file_sha256'))
                    or type(item.get('row_group')) is not int or type(item.get('row_index')) is not int
                    or not isinstance(item.get('column'),str) or not isinstance(item.get('observation_ids'),list)
                    or any(not isinstance(x,str) or not x for x in item['observation_ids'])
                    or len(set(item['observation_ids'])) != len(item['observation_ids'])
                    or not isinstance(item.get('reason'),str) or not item['reason']):
                errors.append('SOURCE_ROW_SHARING_DESCRIPTOR_INVALID')
                continue
            refs = item.get('evidence')
            if not isinstance(refs,list) or not refs or any(not isinstance(r,dict) or not _sha(r.get('file_sha256'))
                    or r['file_sha256'] not in files_by_sha or not r.get('locator') or not r.get('claim') for r in refs):
                errors.append('SOURCE_ROW_SHARING_EVIDENCE_MISSING')
                continue
            token = (item['file_sha256'],item['row_group'],item['row_index'],item['column'])
            if token in allowed:
                errors.append('SOURCE_ROW_SHARING_DESCRIPTOR_DUPLICATE')
            allowed[token] = set(item['observation_ids'])
    used_shares = set()
    for token, entries in claims.items():
        ids = {oid for oid,_ in entries}
        for oid in ids:
            fields = {field for owner,field in entries if owner == oid and field != '__ANCHOR__'}
            if len(fields) > 1:
                errors.append('SOURCE_CELL_BOUND_TO_MULTIPLE_TYPED_FIELDS:'+oid)
        if len(ids) > 1:
            if allowed.get(token) != ids:
                errors.append('SOURCE_COMPONENT_REUSE_NOT_REVIEWED')
            else:
                used_shares.add(token)
    if set(allowed) != used_shares:
        errors.append('SOURCE_ROW_SHARING_SCOPE_MISMATCH')
    return errors


def component_review_errors(bound, proof, files_by_sha):
    """Overall review never fills auxiliary sensor, QC or availability facts."""
    errors=[]
    for field in COMPONENT_REQUIRED_STRINGS:
        if not isinstance(bound.get(field),str) or not bound[field].strip():
            errors.append('SOURCE_TYPED_COMPONENT_MISSING_'+field.upper())
    for field in ('source_qc_raw','source_mqc_raw','source_n1_aqc_raw','source_receive_time_raw'):
        if field not in bound or (bound[field] is not None and not isinstance(bound[field],str)):
            errors.append('SOURCE_TYPED_COMPONENT_LITERAL_REQUIRED_'+field.upper())
    if bound.get('training_value_status') != 'ACCEPTED' or bound.get('source_qc_interpretation') != 'ACCEPTED':
        errors.append('SOURCE_TYPED_COMPONENT_QC_UNRESOLVED')
    if any(bound.get(f)!=proof.get(f) for f in ('physical_sensor_id','sensor_episode_id','event_id','timezone','source_clock_semantics')):
        errors.append('SOURCE_TYPED_COMPONENT_SENSOR_EPISODE_CLOCK_MISMATCH')
    if bound.get('source_clock_semantics')!='OBSERVED_AT':
        errors.append('SOURCE_TYPED_COMPONENT_CLOCK_SEMANTICS_UNRESOLVED')
    sha=bound.get('source_qc_codebook_sha256')
    if not _sha(sha) or files_by_sha.get(sha,{}).get('role')!='QC_CODEBOOK':
        errors.append('SOURCE_TYPED_COMPONENT_CODEBOOK_UNBOUND')
    evidence=bound.get('field_evidence')
    required=COMPONENT_REQUIRED_EVIDENCE+tuple(f for f in ('source_sensor_column','source_episode_column','source_column_map') if f in bound)+(('source_receive_timezone',) if bound.get('source_receive_clock_policy')=='LOCAL_RECEIVE_TIMEZONE' else ())
    for field in required:
        refs=evidence.get(field) if isinstance(evidence,dict) else None
        if not isinstance(refs,list) or not refs or any(not isinstance(r,dict) or not _sha(r.get('file_sha256'))
                or r['file_sha256'] not in files_by_sha or not isinstance(r.get('locator'),str) or not r['locator']
                or not isinstance(r.get('claim'),str) or not r['claim'] for r in refs):
            errors.append('SOURCE_TYPED_COMPONENT_EVIDENCE_MISSING_'+field.upper())
    try:
        stamp=_clock(bound['timestamp_utc'])
        if stamp!=_clock(proof['timestamp_utc']):
            errors.append('SOURCE_TYPED_COMPONENT_TIMESTAMP_MISMATCH')
        for first,last in (('effective_start','effective_end'),('qc_effective_start','qc_effective_end')):
            if not _clock(bound[first])<=stamp<_clock(bound[last]):
                errors.append('SOURCE_TYPED_COMPONENT_PERIOD_MISMATCH')
        available,qc_available=_clock(bound['available_at']),_clock(bound['qc_available_at'])
        if (available<stamp or qc_available<available or available>_clock(proof['available_at'])
                or qc_available>_clock(proof['qc_available_at'])):
            errors.append('SOURCE_TYPED_COMPONENT_AVAILABILITY_MISMATCH')
        received=_receive_utc(bound)
        if received is not None and received>available:
            errors.append('SOURCE_TYPED_COMPONENT_AVAILABLE_BEFORE_RECEIVED')
    except (KeyError,TypeError,ValueError,ZoneInfoNotFoundError):
        errors.append('SOURCE_TYPED_COMPONENT_CLOCK_PERIOD_AVAILABILITY_INCOMPLETE')
    return errors


def _same_depth(first,last):
    return (isinstance(first,dict) and isinstance(last,dict) and set(first)==set(last)=={'step','from','to'}
        and all(type(first[k]) is type(last[k]) and first[k]==last[k] for k in first))


def typed_depth_pairing_errors(proof):
    """Explicit matching bins only; no cross-depth pairing or sorting."""
    bindings=proof.get('typed_payload_bindings')
    fields=bindings.get('fields') if isinstance(bindings,dict) else None
    if not isinstance(fields,dict):
        return ['SOURCE_TYPED_BINDING_FIELDS_INVALID']
    kind=proof.get('quantity_kind')
    if kind=='PROFILE_BINS':
        groups=[fields.get(f) for f in ('bin_ids','depths','values')]
        if any(not isinstance(g,list) or not g for g in groups) or len({len(g) for g in groups})!=1:
            return ['SOURCE_PROFILE_BIN_BINDING_ALIGNMENT_INCOMPLETE']
        if any(not isinstance(b,dict) for g in groups for b in g):
            return ['SOURCE_PROFILE_BIN_BINDING_ALIGNMENT_INCOMPLETE']
        if any(not _same_depth(groups[0][i].get('depth'),groups[n][i].get('depth')) for i in range(len(groups[0])) for n in (1,2)):
            return ['SOURCE_PROFILE_BIN_DEPTH_PAIRING_MISMATCH']
    else:
        for entry in fields.values():
            for binding in entry if isinstance(entry,list) else [entry]:
                if not isinstance(binding,dict) or not _same_depth(binding.get('depth'),proof.get('depth')):
                    return ['SOURCE_TYPED_COMPONENT_DEPTH_PAIRING_MISMATCH']
    return []


def _parquet_row(path, group, index, columns, row_cache=None):
    import pyarrow.parquet as pq
    file = pq.ParquetFile(path)
    if (type(group) is not int or type(index) is not int or group < 0 or index < 0
            or group >= file.num_row_groups or file.metadata.row_group(group).num_rows > 200000
            or index >= file.metadata.row_group(group).num_rows):
        raise SourceContractError('SOURCE_ROW_LOCATOR_OUT_OF_RANGE')
    present = tuple(c for c in columns if c in file.schema_arrow.names)
    key = (str(path), group, present)
    table = row_cache.get(key) if row_cache is not None else None
    if table is None:
        table = file.read_row_group(group, columns=list(present))
        if row_cache is not None:
            row_cache[key] = table
            while len(row_cache) > 4 or sum(t.nbytes for t in row_cache.values()) > 128 * 1024 * 1024:
                row_cache.popitem(last=False)
    elif row_cache is not None:
        row_cache.move_to_end(key)
    return table.slice(index, 1).to_pylist()[0]


def _verified_source_path(proof, files_by_sha, root):
    """Every anchor and typed component has its own RAW/manifest lineage."""
    source = files_by_sha[proof['source_sha256']]
    parquet = files_by_sha[proof['parquet_sha256']]
    manifest_descriptor = files_by_sha[proof['source_manifest_sha256']]
    if (source.get('role') != 'RAW' or parquet.get('role') != 'PARQUET'
            or manifest_descriptor.get('role') != 'SOURCE_MANIFEST'):
        raise SourceContractError('SOURCE_COMPONENT_LINEAGE_ROLES_INVALID')
    manifest = _json_file(_path(root, manifest_descriptor['path']))
    format = manifest_descriptor.get('format', 'SHARE_RAW_V1')
    if manifest.get('source_sha256') != source['sha256'] or manifest.get('source_size') != source['bytes']:
        raise SourceContractError('SOURCE_MANIFEST_LINEAGE_MISMATCH')
    source_path = manifest.get('path') if format == 'MONTHLY_SQLPLUS_RAW_V1' else manifest.get('source_path')
    if source.get('availability') in {'ORIGINAL_DELETED', 'PRESERVED_ALIAS'} and source_path != source.get('original_path'):
        raise SourceContractError('DELETED_RAW_ORIGINAL_PATH_MISMATCH')
    path = _path(root, parquet['path'])
    if format == 'MONTHLY_SQLPLUS_RAW_V1':
        if manifest.get('status') != 'RAW_PARSED_RECONCILED':
            raise SourceContractError('SQLPLUS_MANIFEST_NOT_RECONCILED')
        base = _path(root, manifest_descriptor.get('parquet_root'))
        if not isinstance(manifest.get('files'),list) or any(not isinstance(f,dict) for f in manifest['files']):
            raise SourceContractError('SQLPLUS_MANIFEST_FILES_INVALID')
        matched = [f for f in manifest['files'] if f.get('sha256') == parquet['sha256']
            and _path(base, f.get('path')) == path]
        if len(matched) != 1:
            raise SourceContractError('PARQUET_MANIFEST_PATH_MISMATCH')
    elif format == 'SHARE_RAW_V1':
        if (manifest.get('raw_sha256') != parquet['sha256'] or manifest.get('source_system') != proof['source_group']
                or Path(manifest.get('raw_path', '')).resolve() != path.resolve()):
            raise SourceContractError('PARQUET_MANIFEST_PATH_MISMATCH')
    else:
        raise SourceContractError('SOURCE_MANIFEST_ADAPTER_UNDEFINED')
    return path, format


def _depth_from(row, proof):
    """An alternative physical column requires an explicit reviewed mapping."""
    mapping = proof.get('source_column_map')
    if 'FR_DEPTH' in row:
        if (not isinstance(mapping,dict) or not isinstance(mapping.get('depth_from'),str)
                or mapping['depth_from'] not in {'FR_DEPTH','FROM_DEPTH'}):
            raise SourceContractError('SOURCE_DEPTH_COLUMN_MAP_REQUIRED')
        if 'FROM_DEPTH' in row and (type(row['FR_DEPTH']) is not type(row['FROM_DEPTH']) or row['FR_DEPTH'] != row['FROM_DEPTH']):
            raise SourceContractError('SOURCE_DEPTH_COLUMN_ALIAS_CONFLICT')
    selected = mapping.get('depth_from') if isinstance(mapping,dict) else 'FROM_DEPTH'
    if mapping is not None and selected not in row:
        raise SourceContractError('SOURCE_DEPTH_COLUMN_MAP_ABSENT')
    return row.get(selected)


def verify_source_row(proof, files_by_sha, root=None, *, row_cache=None):
    """Read a bounded row group; source strings, spaces and NULL stay intact."""
    import pyarrow.parquet as pq
    root = root or SOURCE_ROOT
    match = re.fullmatch(r'parquet_row_group=(0|[1-9]\d*);row_index=(0|[1-9]\d*)', proof['source_row_locator'])
    if not match:
        raise SourceContractError('SOURCE_ROW_LOCATOR_UNSUPPORTED')
    path, format = _verified_source_path(proof,files_by_sha,root)
    group, index = map(int, match.groups())
    columns = ['OBS_POST_ID', 'OBS_ITEM_CODE', 'OBS_TIME', 'OBS_VALUE', 'QC_FLAG', 'MQC_FLAG', 'N1_AQC_FLAG', 'RECEIVE_TIME', 'WATER_STEP', 'FR_DEPTH', 'FROM_DEPTH', 'TO_DEPTH']
    if format == 'MONTHLY_SQLPLUS_RAW_V1':
        source_names = {'station_raw':'OBS_POST_ID', 'item_raw':'OBS_ITEM_CODE', 'time_raw':'OBS_TIME',
            'value_raw':'OBS_VALUE', 'qc_raw':'QC_FLAG', 'mq_raw':'MQC_FLAG', 'n1_aqc_raw':'N1_AQC_FLAG'}
        rawrow = _parquet_row(path, group, index, [*source_names, 'record_class'], row_cache)
        if rawrow.get('record_class') != 'OBSERVATION_SHAPED_UNVALIDATED':
            raise SourceContractError('SQLPLUS_ROW_NOT_OBSERVATION')
        metadata = pq.ParquetFile(path).schema_arrow.metadata or {}
        if metadata.get(b'source_sha256', b'').decode() != proof['source_sha256']:
            raise SourceContractError('SQLPLUS_PARQUET_SOURCE_HASH_MISMATCH')
        row = {target:rawrow.get(key) for key, target in source_names.items()}
    else:
        row = _parquet_row(path, group, index, columns, row_cache)
    if not {'OBS_POST_ID', 'OBS_ITEM_CODE', 'OBS_TIME', 'OBS_VALUE'} <= set(row):
        raise SourceContractError('SOURCE_ROW_SCHEMA_UNSUPPORTED')
    pairs = [('OBS_POST_ID', 'source_station_literal'), ('OBS_ITEM_CODE', 'source_item_literal'),
        ('OBS_TIME', 'source_time_raw'), ('OBS_VALUE', 'source_value_raw'), ('QC_FLAG', 'source_qc_raw'),
        ('MQC_FLAG', 'source_mqc_raw'), ('N1_AQC_FLAG', 'source_n1_aqc_raw'),('RECEIVE_TIME','source_receive_time_raw')]
    for column, field in pairs:
        if field not in proof or type(row.get(column)) is not type(proof[field]) or row.get(column) != proof[field]:
            raise SourceContractError('SOURCE_LITERAL_MISMATCH', column)
    for column, field, kind in [('OBS_POST_ID', 'source_station_code', 'station'), ('OBS_ITEM_CODE', 'source_item_code', 'item')]:
        value = row[column].strip() if proof['source_identifier_transform'][kind] == 'STRIP_SQLPLUS_PADDING' else row[column]
        if value != proof[field]:
            raise SourceContractError('SOURCE_IDENTIFIER_TRANSFORM_MISMATCH', column)
    for column, field in [('WATER_STEP', 'step'), ('FROM_DEPTH', 'from'), ('TO_DEPTH', 'to')]:
        actual = _depth_from(row,proof) if field == 'from' else row.get(column)
        if type(actual) is not type(proof['depth'][field]) or actual != proof['depth'][field]:
            raise SourceContractError('SOURCE_TYPED_DEPTH_MISMATCH', column)
    if _local_clock(proof['source_time_raw'],proof['timezone']) != _clock(proof['timestamp_utc']):
        raise SourceContractError('SOURCE_CLOCK_CONVERSION_MISMATCH')
    if proof['quantity_kind'] == 'SCALAR':
        value = _number(proof['source_value_raw']) * _number(proof['quantity_transform']['scale']) + _number(proof['quantity_transform']['offset'])
        if value != _number(proof['value']):
            raise SourceContractError('SOURCE_QUANTITY_CONVERSION_MISMATCH')
    else:
        verify_typed_payload(proof, files_by_sha, root, row_cache=row_cache)
    received=_receive_utc(proof)
    if received is not None and received>_clock(proof['available_at']):
        raise SourceContractError('SOURCE_AVAILABLE_BEFORE_RECEIVED')
    return row


def verify_typed_payload(proof, files_by_sha, root=None, *, row_cache=None):
    """Explicit component rows only: no inferred pairing, sorting or filling."""
    import pyarrow.parquet as pq
    root = root or SOURCE_ROOT
    payload, bindings = proof['typed_payload'], proof['typed_payload_bindings']
    kind = proof['quantity_kind']
    errors=typed_depth_pairing_errors(proof)
    if errors:
        raise SourceContractError(errors[0])
    for field in TYPED_FIELDS[kind]:
        original = bindings['fields'][field]
        many = isinstance(original, list)
        entries = original if many else [original]
        values = []
        if not entries:
            raise SourceContractError('SOURCE_TYPED_BINDING_EMPTY', field)
        for bound in entries:
            errors=component_review_errors(bound,proof,files_by_sha)
            if errors:
                raise SourceContractError('SOURCE_TYPED_COMPONENT_REVIEW_INCOMPLETE',','.join(errors))
            descriptor = files_by_sha.get(bound.get('file_sha256'), {})
            if descriptor.get('role') != 'PARQUET':
                raise SourceContractError('SOURCE_TYPED_COMPONENT_FILE_UNBOUND', field)
            if (type(bound.get('row_group')) is not int or type(bound.get('row_index')) is not int
                    or bound['row_group'] < 0 or bound['row_index'] < 0):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_LOCATOR_INVALID', field)
            lineage = {'source_sha256':bound.get('source_sha256'), 'parquet_sha256':bound.get('file_sha256'),
                'source_manifest_sha256':bound.get('source_manifest_sha256'), 'source_group':bound.get('source_group')}
            if not _sha(lineage['source_sha256']) or not _sha(lineage['source_manifest_sha256']):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_LINEAGE_MISSING',field)
            path, format = _verified_source_path(lineage,files_by_sha,root)
            source = pq.ParquetFile(path)
            group, index = bound['row_group'], bound['row_index']
            if (group >= source.num_row_groups or source.metadata.row_group(group).num_rows > 200000
                    or index >= source.metadata.row_group(group).num_rows):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_LOCATOR_OUT_OF_RANGE', field)
            column = bound.get('column')
            if not isinstance(column, str) or column not in source.schema_arrow.names:
                raise SourceContractError('SOURCE_TYPED_COMPONENT_COLUMN_MISSING', field)
            names = {'station_raw':'OBS_POST_ID','item_raw':'OBS_ITEM_CODE','time_raw':'OBS_TIME',
                'qc_raw':'QC_FLAG','mq_raw':'MQC_FLAG','n1_aqc_raw':'N1_AQC_FLAG'} if format == 'MONTHLY_SQLPLUS_RAW_V1' else {}
            sensor_columns=[]
            for canonical,mapping in (('PHYSICAL_SENSOR_ID','source_sensor_column'),('SENSOR_EPISODE_ID','source_episode_column')):
                selected=bound.get(mapping)
                if canonical in source.schema_arrow.names and selected is None:
                    raise SourceContractError('SOURCE_TYPED_SENSOR_COLUMN_MAP_REQUIRED',canonical)
                if selected is not None:
                    if not isinstance(selected,str) or selected not in source.schema_arrow.names:
                        raise SourceContractError('SOURCE_TYPED_SENSOR_COLUMN_MAP_INVALID',mapping)
                    sensor_columns.append(selected)
            columns = list(dict.fromkeys([column] + list(names) + ['record_class'] + sensor_columns + [c for c in ('OBS_POST_ID', 'OBS_ITEM_CODE', 'OBS_TIME', 'QC_FLAG','MQC_FLAG','N1_AQC_FLAG','RECEIVE_TIME','WATER_STEP', 'FR_DEPTH', 'FROM_DEPTH', 'TO_DEPTH') if c in source.schema_arrow.names]))
            rawrow = _parquet_row(path, group, index, columns, row_cache)
            row = {**rawrow, **{target:rawrow.get(key) for key,target in names.items()}}
            if format == 'MONTHLY_SQLPLUS_RAW_V1' and (rawrow.get('record_class') != 'OBSERVATION_SHAPED_UNVALIDATED'
                    or (source.schema_arrow.metadata or {}).get(b'source_sha256',b'').decode() != bound['source_sha256']):
                raise SourceContractError('SOURCE_TYPED_SQLPLUS_LINEAGE_MISMATCH',field)
            for column_name,proof_field in (('QC_FLAG','source_qc_raw'),('MQC_FLAG','source_mqc_raw'),
                    ('N1_AQC_FLAG','source_n1_aqc_raw'),('RECEIVE_TIME','source_receive_time_raw')):
                if type(row.get(column_name)) is not type(bound[proof_field]) or row.get(column_name)!=bound[proof_field]:
                    raise SourceContractError('SOURCE_TYPED_COMPONENT_QC_RECEIVE_LITERAL_MISMATCH',column_name)
            for mapping,identity in (('source_sensor_column','physical_sensor_id'),('source_episode_column','sensor_episode_id')):
                if mapping in bound and (type(row[bound[mapping]]) is not type(bound[identity]) or row[bound[mapping]]!=bound[identity]):
                    raise SourceContractError('SOURCE_TYPED_COMPONENT_RAW_SENSOR_EPISODE_MISMATCH',mapping)
            identifier = bound.get('source_identifier_transform')
            if (not isinstance(identifier,dict) or set(identifier) != {'station','item'}
                    or any(not isinstance(v,str) or v not in {'IDENTITY','STRIP_SQLPLUS_PADDING'} for v in identifier.values())):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_IDENTIFIER_TRANSFORM_MISSING',field)
            station = row.get('OBS_POST_ID')
            item = row.get('OBS_ITEM_CODE')
            if (not isinstance(station,str) or not isinstance(item,str)
                    or station != bound.get('source_station_literal') or item != bound.get('source_item_literal')
                    or (station.strip() if identifier['station'] == 'STRIP_SQLPLUS_PADDING' else station) != bound.get('source_station_code')
                    or (item.strip() if identifier['item'] == 'STRIP_SQLPLUS_PADDING' else item) != bound.get('source_item_code')
                    or row.get('OBS_TIME') != bound.get('source_time_raw')
                    or bound.get('source_station_code') != proof['source_station_code']
                    or bound.get('source_group') != proof['source_group']):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_IDENTITY_MISMATCH', field)
            for name, depth in (('WATER_STEP', 'step'), ('FROM_DEPTH', 'from'), ('TO_DEPTH', 'to')):
                actual = _depth_from(row,bound) if depth == 'from' else row.get(name)
                if type(actual) is not type(bound['depth'][depth]) or actual != bound['depth'][depth]:
                    raise SourceContractError('SOURCE_TYPED_COMPONENT_DEPTH_MISMATCH', field)
            if _local_clock(row['OBS_TIME'],proof['timezone']) != _clock(proof['timestamp_utc']):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_CLOCK_MISMATCH', field)
            if field == 'bin_ids':
                value = row[column]
            else:
                expected_unit = ('degree' if kind in {'CIRCULAR_DEGREES', 'TRAJECTORY'} and field in {'value', 'longitude', 'latitude'}
                    else payload.get('magnitude_unit') if field == 'magnitude'
                    else 'm' if field == 'depths' else proof['unit'])
                if not bound.get('source_unit') or bound.get('unit') != expected_unit:
                    raise SourceContractError('SOURCE_TYPED_COMPONENT_UNIT_UNBOUND', field)
                value = _number(row[column]) * _number(bound.get('scale')) + _number(bound.get('offset'))
            values.append(value)
        claimed = payload.get(field)
        if many:
            if not isinstance(claimed, list) or len(claimed) != len(values):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_LENGTH_MISMATCH', field)
            if any((type(a) is not type(b) or a != b) if field == 'bin_ids' else _number(a) != b for a, b in zip(claimed, values)):
                raise SourceContractError('SOURCE_TYPED_COMPONENT_VALUE_MISMATCH', field)
        elif field == 'bin_ids' or _number(claimed) != values[0]:
            raise SourceContractError('SOURCE_TYPED_COMPONENT_VALUE_MISMATCH', field)
    if kind == 'PROFILE_BINS':
        if (len(payload['bin_ids']) != len(payload['depths']) or len(payload['bin_ids']) != len(payload['values'])
                or len(set(payload['bin_ids'])) != len(payload['bin_ids'])):
            raise SourceContractError('SOURCE_PROFILE_BIN_LAYOUT_INVALID')
        if (payload['unit'] != proof['unit'] or payload['target_variable'] != proof['standard_variable']
                or payload['value_representation'] not in {'SCALAR','CIRCULAR_DEGREES'}):
            raise SourceContractError('SOURCE_PROFILE_VARIABLE_UNIT_REPRESENTATION_MISMATCH')
        if payload['value_representation'] == 'CIRCULAR_DEGREES' and any(not 0 <= _number(v) < 360 for v in payload['values']):
            raise SourceContractError('SOURCE_PROFILE_CIRCULAR_DOMAIN_INVALID')
    if kind == 'CIRCULAR_DEGREES' and (not 0 <= _number(payload['value']) < 360 or _number(payload['magnitude']) < 0):
        raise SourceContractError('SOURCE_CIRCULAR_DOMAIN_INVALID')
    if kind == 'SIGNED_RADIAL' and (payload['qc_eligible'] is not True or not 0 <= _number(payload['coverage_fraction']) <= 1):
        raise SourceContractError('SOURCE_RADIAL_COVERAGE_INVALID')
    if kind == 'TRAJECTORY' and (payload['coordinate_frame'] != 'WGS84'
            or not -180 <= _number(payload['longitude']) <= 180 or not -90 <= _number(payload['latitude']) <= 90):
        raise SourceContractError('SOURCE_TRAJECTORY_DOMAIN_INVALID')


def request_contract(db, packet, actor):
    if actor.role not in {'operator', 'reviewer', 'admin'} or not actor.user_id:
        raise SourceContractError('AUTHENTICATED_OPERATOR_REQUIRED')
    errors = packet_errors(packet)
    if any(x in errors for x in ('SOURCE_CONTRACT_SCHEMA_INVALID', 'SOURCE_CONTRACT_PACKET_TOO_LARGE',
            'SOURCE_CONTRACT_JSON_INVALID', 'CONTRACT_ID_INVALID', 'CALLER_APPROVAL_FIELDS_FORBIDDEN')):
        raise SourceContractError('INVALID_REVIEW_PACKET', ','.join(errors))
    if db.get(SourceContractPacket, packet['contract_id']) is not None:
        raise SourceContractError('IMMUTABLE_CONTRACT_ID_ALREADY_EXISTS')
    sha = receipt_sha256(packet)
    row = SourceContractPacket(contract_id=packet['contract_id'], payload=packet, packet_sha256=sha,
        requested_by=actor.user_id, status='PENDING')
    db.add(row)
    db.add(ApprovalHistory(approval_type='SOURCE_CONTRACT', target_id=row.contract_id,
        requested_by=actor.user_id, approved_by=None, approval_status='PENDING', comment='packet_sha256=' + sha))
    db.flush()
    return {'contract_id':row.contract_id, 'status':'PENDING', 'packet_sha256':sha,
        'approval_complete':False, 'readiness_errors':errors}


def decide_contract(db, contract_id, expected_packet_sha256, decision, actor, comment='', root=None):
    if actor.role not in {'reviewer', 'admin'} or not actor.user_id:
        raise SourceContractError('AUTHENTICATED_REVIEWER_REQUIRED')
    packet = db.execute(select(SourceContractPacket).where(SourceContractPacket.contract_id == contract_id).with_for_update()).scalar_one_or_none()
    if packet is None:
        raise SourceContractError('SOURCE_CONTRACT_NOT_FOUND')
    if receipt_sha256(packet.payload) != packet.packet_sha256 or expected_packet_sha256 != packet.packet_sha256:
        raise SourceContractError('REVIEW_PACKET_HASH_MISMATCH')
    if decision not in {'APPROVED', 'REJECTED', 'REVOKED'}:
        raise SourceContractError('SOURCE_DECISION_UNSUPPORTED')
    if (decision in {'APPROVED', 'REJECTED'} and packet.status != 'PENDING') or (decision == 'REVOKED' and packet.status != 'APPROVED'):
        raise SourceContractError('SOURCE_CONTRACT_ALREADY_DECIDED')
    errors = packet_errors(packet.payload, root=root, verify_sources=decision == 'APPROVED')
    if decision == 'APPROVED' and errors:
        raise SourceContractError('SOURCE_CONTRACT_APPROVAL_BLOCKED', json.dumps(errors, ensure_ascii=False))
    history = ApprovalHistory(approval_type='SOURCE_CONTRACT', target_id=contract_id,
        requested_by=packet.requested_by, approved_by=actor.user_id if decision == 'APPROVED' else None,
        approval_status=decision, comment='')
    db.add(history)
    db.flush()
    receipt = {'schema_version':EXPORT_SCHEMA, 'source_contract_schema':SCHEMA, 'contract_id':contract_id,
        'packet_sha256':packet.packet_sha256, 'requested_by':packet.requested_by, 'status':decision, 'approval_complete':decision == 'APPROVED',
        'approved_by':actor.user_id if decision == 'APPROVED' else None,
        'source_availability_policy':packet.payload.get('source_availability_policy'),
        'source_row_reuse_policy':packet.payload.get('source_row_reuse_policy'),
        'scope':packet.payload.get('scope', []), 'files':packet.payload.get('files', []),
        'observations':packet.payload.get('observations', {}), 'validation_errors':errors,
        'approval_receipt':{'approval_history_id':history.id, 'approval_type':'SOURCE_CONTRACT', 'target_id':contract_id,
            'reviewer_id':actor.user_id, 'reviewer_role':actor.role, 'decision':decision,
            'decided_at':datetime.now(timezone.utc).isoformat(), 'comment':comment},
        'approval_scope':'SOURCE_IDENTITY_UNIT_CLOCK_QC_RULE_EVIDENCE_ONLY; DATASET_LABEL_MODEL_APPROVALS_SEPARATE'}
    sha = receipt_sha256(receipt)
    history.comment = 'snapshot_sha256=' + sha
    db.add(SourceContractDecision(approval_history_id=history.id, contract_id=contract_id,
        packet_sha256=packet.packet_sha256, decision=decision, reviewer_id=actor.user_id,
        reviewer_role=actor.role, receipt_sha256=sha, receipt=receipt))
    packet.status = decision
    db.flush()
    return {'contract_id':contract_id, 'status':decision, 'receipt_sha256':sha, 'receipt':receipt}


def verify_approved_receipt(db, receipt, receipt_sha256_value, *, verify_sources=True, root=None):
    """Authoritative approval, including subsequent revocation and tampering."""
    sha = receipt_sha256(receipt)
    if sha != receipt_sha256_value or receipt.get('schema_version') != EXPORT_SCHEMA or receipt.get('source_contract_schema') != SCHEMA:
        raise SourceContractError('APPROVED_RECEIPT_HASH_OR_SCHEMA_MISMATCH')
    contract_id = receipt.get('contract_id')
    packet = db.get(SourceContractPacket, contract_id)
    history = db.query(ApprovalHistory).filter_by(approval_type='SOURCE_CONTRACT', target_id=contract_id).order_by(ApprovalHistory.id.desc()).first()
    approval = receipt.get('approval_receipt', {})
    row = db.get(SourceContractDecision, approval.get('approval_history_id'))
    if not packet or not history or not row:
        raise SourceContractError('SOURCE_APPROVAL_LEDGER_MISSING')
    request = db.query(ApprovalHistory).filter_by(approval_type='SOURCE_CONTRACT', target_id=contract_id, approval_status='PENDING').order_by(ApprovalHistory.id).first()
    if (not request or request.id >= history.id or request.approved_by is not None
            or request.requested_by != packet.requested_by or history.requested_by != packet.requested_by
            or receipt.get('requested_by') != packet.requested_by or request.comment != 'packet_sha256=' + packet.packet_sha256):
        raise SourceContractError('SOURCE_REQUEST_LEDGER_MISMATCH')
    if (packet.status != 'APPROVED' or history.approval_status != 'APPROVED' or row.decision != 'APPROVED'
            or receipt.get('status') != 'APPROVED' or receipt.get('approval_complete') is not True):
        raise SourceContractError('SOURCE_APPROVAL_NOT_CURRENT')
    if (history.id != row.approval_history_id or history.id != approval.get('approval_history_id')
            or history.comment != 'snapshot_sha256=' + sha or row.receipt_sha256 != sha
            or receipt_sha256(row.receipt) != sha or row.receipt != receipt):
        raise SourceContractError('SOURCE_APPROVAL_LEDGER_HASH_MISMATCH')
    if (not history.approved_by or history.approved_by != receipt.get('approved_by')
            or row.reviewer_id != history.approved_by or approval.get('reviewer_id') != history.approved_by
            or row.reviewer_role not in {'reviewer', 'admin'} or approval.get('reviewer_role') != row.reviewer_role
            or approval.get('decision') != 'APPROVED' or approval.get('approval_type') != 'SOURCE_CONTRACT'
            or row.contract_id != contract_id or approval.get('target_id') != contract_id):
        raise SourceContractError('SOURCE_APPROVAL_ACTOR_MISMATCH')
    if (receipt_sha256(packet.payload) != packet.packet_sha256 or row.packet_sha256 != packet.packet_sha256
            or receipt.get('packet_sha256') != packet.packet_sha256 or packet_errors(packet.payload, root=root, verify_sources=verify_sources)):
        raise SourceContractError('SOURCE_APPROVED_PACKET_CHANGED_OR_INCOMPLETE')
    for field in ('source_availability_policy', 'source_row_reuse_policy', 'scope', 'files', 'observations'):
        if canonical_bytes(receipt.get(field)) != canonical_bytes(packet.payload.get(field)):
            raise SourceContractError('SOURCE_RECEIPT_PACKET_CONTENT_MISMATCH', field)
    if receipt.get('validation_errors') != []:
        raise SourceContractError('SOURCE_RECEIPT_VALIDATION_ERRORS')
    return {'contract_id':contract_id, 'approval_history_id':history.id, 'reviewer_id':history.approved_by,
        'packet_sha256':packet.packet_sha256, 'receipt_sha256':sha}
