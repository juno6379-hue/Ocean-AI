"""Read-only QC review, with exact source lineage and no inference side effects.

Archive rows are samples, never registered QC candidates. Current mutable
metadata and unversioned DB clocks cannot become historical equipment/AI proof.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import math
import re
from types import SimpleNamespace

from sqlalchemy import inspect, or_, and_, tuple_, text
from app.core.config import settings
from app.core.security import Actor
from app.models.domain import (ObservationStandard, ObservationRaw, QCRuleResult,
    QCRuleDefinition, AIPredictionResult, ModelRegistry, OperationLog, DocumentIndex,DailyInspectionReport)
from app.models.source_observation_binding import SourceObservationBinding
from app.models.source_contracts import SourceContractDecision
from app.models.agent_workflow import AgentWorkflowRun, AgentWorkflowTransition
from app.services import qc_rule_engine as engine
from app.services.observation_provenance import source_issue
from app.services.source_contract_authority import verify_approved_receipt, SourceContractError
from app.services.source_contract_review import exact_scope_key

SCHEMA = 'qc-candidate-review-1'
MAX_ROWS = 10000
CHART_LIMIT = 3000
SHA = re.compile(r'^[0-9a-f]{64}$')
SCOPE_KEYS = ('station_id', 'sensor_id', 'variable_code', 'unit', 'physical_sensor_id', 'sensor_episode_id')
TABLES = ('source_observation_binding', 'observation_standard', 'observation_raw',
    'source_contract_packets', 'source_contract_decisions', 'approval_history')
FLAGS = {'1': ('GOOD', '정상', 3), '3': ('SUSPECT', '주의/의심', 1),
    '4': ('BAD', 'BAD', 0), '9': ('MISSING', '결측', 2),
    'NOT_EVALUATED': ('NOT_EVALUATED', '미평가', 4)}


class CandidateError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _json(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def digest(value): return engine.digest(_json(value))


def _aware(value):
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset() is None: raise ValueError()
        return stamp.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise CandidateError('EXPLICIT_OFFSET_CLOCK_REQUIRED') from None


def _utc_column(value):
    # Only timestamp_utc has an explicit UTC storage contract. No created_at,
    # receive_time or arbitrary document timestamp receives this conversion.
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return _aware(value)


def _finite(value):
    if type(value) not in {int, float, str}: return None
    try:
        number = float(Decimal(str(value)))
        return number if math.isfinite(number) else None
    except (ValueError, InvalidOperation, OverflowError): return None


def _same_number(a, b):
    try: return Decimal(str(a)).is_finite() and Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation: return False


def _payload(value):
    if isinstance(value, dict): return value
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError): return {}


def flag_catalog():
    """Mappings are for this engine's result column, not a global source codebook."""
    result = dict(schema_version='qc-flag-catalog-1', engine_version=engine.ENGINE_VERSION,
        namespace='QCRuleResult.result_flag', source='app.services.qc_rule_engine',
        flags=[dict(code=code, meaning=meaning, label=label, queue_priority=priority)
               for code, (meaning, label, priority) in FLAGS.items()],
        unknown=dict(meaning='UNKNOWN', label='미확인/기타'),
        source_qc=dict(interpreted=False, reason='EXACT_SOURCE_CODEBOOK_REQUIRED'),
        approval_codes=dict(accepted=['1','2','3','4','9','G','S','B','GOOD','SUSPECT','BAD','MISSING'],
                            meaning_policy='ACCEPTED_VALUES_ARE_NOT_A_SOURCE_CODEBOOK'),
        rules=engine.catalog()['rules'], recipe=engine.implementation_hashes())
    from app.services.qc_overview import flag_catalog as display_catalog
    result['display_catalog']=display_catalog()
    result['catalog_sha256'] = digest(result)
    return result


def begin_readonly_snapshot(db):
    """Set the existing request transaction before its first data query.

    PostgreSQL SELECTs must share a snapshot; this is transaction setup, not a
    data write. Isolated SQLite tests use their own fixture database only.
    """
    dialect=db.get_bind().dialect.name
    if dialect=='postgresql':
        if db.in_transaction():
            isolation=db.execute(text('SHOW transaction_isolation')).scalar_one().upper()
            readonly=db.execute(text('SHOW transaction_read_only')).scalar_one()
            if isolation not in {'REPEATABLE READ','SERIALIZABLE'} or readonly!='on':
                raise CandidateError('READONLY_SNAPSHOT_REQUIRES_FRESH_TRANSACTION')
            return dict(dialect=dialect,isolation=isolation,read_only=True,reused=True,
                authority_basis='CONSISTENT_REQUEST_DB_SNAPSHOT_AND_VERIFIED_SOURCE_FILES')
        db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        return dict(dialect=dialect,isolation='REPEATABLE READ',read_only=True,
            authority_basis='CONSISTENT_REQUEST_DB_SNAPSHOT_AND_VERIFIED_SOURCE_FILES')
    if dialect=='sqlite':
        return dict(dialect=dialect,isolation='ISOLATED_TEST_DATABASE',read_only_service=True,
            authority_basis='TEST_FIXTURE_ONLY_NOT_PRODUCTION_SNAPSHOT')
    raise CandidateError('READONLY_SNAPSHOT_DIALECT_UNSUPPORTED')


def _window_clocks(window):
    if window.get('source') != 'REGISTERED': raise CandidateError('REGISTERED_SOURCE_REQUIRED')
    if window.get('clock_basis') != 'SERVER_LOCAL_OFFSET': raise CandidateError('REGISTERED_CLOCK_BASIS_REQUIRED')
    start, end, cutoff = (_aware(window.get(k)) for k in ('start', 'end', 'as_of'))
    if start > end or end > cutoff: raise CandidateError('INVALID_WINDOW')
    return start, end, cutoff


def _scope(row): return {key: row[key] for key in SCOPE_KEYS} | {'depth': row['depth']}


def _registered_row(observation, binding, receipt, raw, window):
    start, end, cutoff = _window_clocks(window)
    proof = binding.payload
    if not isinstance(proof, dict) or receipt.get('observations', {}).get(observation.observation_id) != proof:
        raise CandidateError('APPROVED_PROOF_NOT_EXACT_OBSERVATION')
    if (binding.contract_id != receipt.get('contract_id') or binding.approval_history_id != receipt.get('approval_receipt', {}).get('approval_history_id')):
        raise CandidateError('BINDING_APPROVAL_MISMATCH')
    issue = source_issue(raw)
    if issue: raise CandidateError(issue.upper())
    for key in ('source_sha256', 'parquet_sha256', 'source_row_locator', 'exact_scope_key'):
        if getattr(binding, key) != proof.get(key): raise CandidateError('BINDING_' + key.upper() + '_MISMATCH')
    if any(getattr(observation, key) != proof.get(target) for key, target in (
            ('station_id','canonical_station_id'), ('sensor_id','canonical_sensor_id'),
            ('variable_code','standard_variable'), ('standard_unit','unit'), ('source_item_code','source_item_code'))):
        raise CandidateError('CANONICAL_OBSERVATION_SCOPE_MISMATCH')
    stamp = _utc_column(observation.timestamp_utc)
    if stamp != _aware(proof.get('timestamp_utc')) or not start <= stamp <= end:
        raise CandidateError('OBSERVATION_OUTSIDE_WINDOW_OR_CLOCK_MISMATCH')
    if proof.get('quantity_kind') != 'SCALAR' or not _same_number(observation.value_standard, proof.get('value')):
        raise CandidateError('SCALAR_VALUE_MISMATCH_OR_UNSUPPORTED_REPRESENTATION')
    if (raw.source_system != proof.get('source_group') or not _same_number(raw.value_raw, proof.get('source_value_raw'))
            or raw.source_item_code != proof.get('source_item_code') or raw.qc_flag != proof.get('source_qc_raw')
            or raw.mqc_flag != proof.get('source_mqc_raw')):
        raise CandidateError('RAW_SOURCE_RECORD_CHANGED')
    depth = proof.get('depth')
    if not isinstance(depth, dict) or set(depth) != {'step','from','to'}: raise CandidateError('EXACT_TYPED_DEPTH_REQUIRED')
    for key, col in (('step','water_step'),('from','from_depth'),('to','to_depth')):
        # ORM depth columns are Float; the type-sensitive original grain stays
        # in the signed proof and exact_scope_key rather than an ORM float cast.
        if (depth[key] is None) != (getattr(observation,col) is None) or depth[key] is not None and not _same_number(depth[key],getattr(observation,col)):
            raise CandidateError('TYPED_DEPTH_CHANGED')
        if (depth[key] is None) != (getattr(raw,col) is None) or depth[key] is not None and not _same_number(depth[key],getattr(raw,col)): raise CandidateError('RAW_TYPED_DEPTH_CHANGED')
    grain = dict(source_group=proof['source_group'], station_code=proof.get('source_station_code'),
        item_code=proof.get('source_item_code'), month=proof.get('source_month'),
        depth_step=depth['step'], depth_from=depth['from'], depth_to=depth['to'])
    if exact_scope_key(grain) != binding.exact_scope_key: raise CandidateError('EXACT_SOURCE_GRAIN_CHANGED')
    if any(not proof.get(key) for key in ('physical_sensor_id','sensor_episode_id','timezone','qc_rule_version')):
        raise CandidateError('SOURCE_FACTS_INCOMPLETE')
    for first,last in (('effective_start','effective_end'),('qc_effective_start','qc_effective_end')):
        if not _aware(proof.get(first)) <= stamp < _aware(proof.get(last)): raise CandidateError('SOURCE_OR_QC_EPISODE_OUTSIDE_PERIOD')
    available = max(_aware(proof.get('available_at')), _aware(proof.get('qc_available_at')),
                    _aware(receipt.get('approval_receipt', {}).get('decided_at')))
    # A source observation's available_at is not its later DB ingest clock.
    # Only the new explicit-offset ingest clock is authoritative. created_at
    # has no historical timezone contract and is never a fallback/backfill.
    try: binding_available = _aware(getattr(binding,'bound_at_utc',None))
    except CandidateError: raise CandidateError('BINDING_RECORD_AVAILABILITY_UNVERIFIED') from None
    if max(available, binding_available) > cutoff: raise CandidateError('POST_CUTOFF_SOURCE_OR_BINDING_AVAILABLE')
    available=max(available,binding_available)
    received = proof.get('source_receive_timestamp_utc')
    if received is not None:
        received_clock = _aware(received)
        if received_clock > cutoff or received_clock > _aware(proof['available_at']): raise CandidateError('POST_CUTOFF_RECEIPT')
        delay = (received_clock-stamp).total_seconds()/60
        if delay < 0: raise CandidateError('RECEIVED_BEFORE_OBSERVATION')
    else: delay = None
    result = dict(observation_id=observation.observation_id, station_id=observation.station_id,
        sensor_id=observation.sensor_id, variable_code=observation.variable_code, item_code=observation.variable_code,
        source_item_code=proof['source_item_code'], observation_time=proof['timestamp_utc'],
        value=observation.value_standard, value_raw=proof.get('source_value_raw'), unit=proof['unit'],
        received_time=received, delay_minutes=delay, delay_flag='NOT_EVALUATED',
        receive_timing='UNKNOWN' if delay is None else 'RECEIVED_AFTER_OBSERVATION' if delay>0 else 'SAME_TIMESTAMP',
        late_history=[] if delay is None or delay == 0 else [dict(received_time=received, delay_minutes=delay, basis='APPROVED_SOURCE_RECEIVE_COLUMN')],
        available_at=available.isoformat(), source_group=proof['source_group'], source_sha256=binding.source_sha256,
        parquet_sha256=binding.parquet_sha256, source_row_locator=binding.source_row_locator,
        physical_sensor_id=proof['physical_sensor_id'], sensor_episode_id=proof['sensor_episode_id'], depth=depth,
        qc_source_literals={key:proof.get(key) for key in ('source_qc_raw','source_mqc_raw','source_n1_aqc_raw')},
        source_qc_interpreted=False, contract_id=binding.contract_id, receipt_sha256=binding.receipt_sha256,
        source_proof=proof, is_gap=False, is_late=None, actual_value=True)
    result['authority_sha256'] = digest(result)
    return result


def registered_rows(db, window, station='', item='', *, limit=MAX_ROWS, observation_id=None,receipt_cache=None):
    if not 1 <= limit <= MAX_ROWS: raise CandidateError('INVALID_ROW_LIMIT')
    rows=[];excluded=Counter();scanned=0;selected=None;missing=[];cache={} if receipt_cache is None else receipt_cache
    for batch in iter_registered_batches(db,window,station,item,batch_size=min(limit,500),observation_id=observation_id,receipt_cache=cache):
        selected=batch['selected_count'];missing=batch['missing_tables']
        rows.extend(batch['rows']);excluded.update(batch['excluded_counts']);scanned+=batch['scanned_count']
        if scanned>=limit: break
    verify_cached_authority(db,cache)
    truncated=selected is not None and scanned<selected or len(rows)>limit
    return dict(status='TABLES_ABSENT' if missing else 'PARTIAL' if truncated or excluded else 'AVAILABLE' if rows else 'NO_DATA',
        rows=rows[:limit], selected_count=selected, scanned_count=scanned,truncated=truncated,
        excluded_counts=dict(excluded),missing_tables=missing)


def _receipt(db,binding,cache):
    if binding.receipt_sha256 not in cache:
        try:
            decision=db.get(SourceContractDecision,binding.approval_history_id)
            if not decision: raise CandidateError('SOURCE_APPROVAL_LEDGER_MISSING')
            verify_approved_receipt(db,decision.receipt,binding.receipt_sha256)
            cache[binding.receipt_sha256]=dict(receipt=decision.receipt,error=None)
        except (CandidateError,SourceContractError,OSError,ValueError) as exc:
            cache[binding.receipt_sha256]=dict(receipt=None,error=getattr(exc,'code',None) or 'SOURCE_AUTHORITY_UNVERIFIED')
    item=cache[binding.receipt_sha256]
    if item['error']: raise CandidateError(item['error'])
    return item['receipt']


def iter_registered_batches(db, window, station='', item='', *, batch_size=500, receipt_cache=None, observation_id=None,station_scope=None):
    """Keyset census with bounded row memory and request-local receipt reuse.

    The consumer must exhaust this generator for a complete-population claim.
    Count changes fail closed. Unlike the detail wrapper, there is no row cap.
    """
    start, end, _ = _window_clocks(window)
    if not 1<=batch_size<=500: raise CandidateError('INVALID_BATCH_SIZE')
    existing = set(inspect(db.connection()).get_table_names())
    missing = sorted(set(TABLES)-existing)
    if missing:
        yield dict(status='TABLES_ABSENT',rows=[],selected_count=None,scanned_count=0,truncated=False,excluded_counts={},missing_tables=missing)
        return
    query = db.query(ObservationStandard, SourceObservationBinding).join(SourceObservationBinding,
        ObservationStandard.observation_id == SourceObservationBinding.observation_id).filter(
        ObservationStandard.timestamp_utc >= start.astimezone(timezone.utc).replace(tzinfo=None),
        ObservationStandard.timestamp_utc <= end.astimezone(timezone.utc).replace(tzinfo=None))
    if station: query = query.filter(ObservationStandard.station_id == station)
    if item: query = query.filter(ObservationStandard.variable_code == item)
    if observation_id: query = query.filter(ObservationStandard.observation_id == observation_id)
    if station_scope is not None:
        if set(station_scope)=={'include'}: query=query.filter(ObservationStandard.station_id.in_(station_scope['include']))
        elif set(station_scope)=={'exclude'}: query=query.filter(ObservationStandard.station_id.not_in(station_scope['exclude']))
        else: raise CandidateError('INVALID_STATION_SCOPE')
    count=query.count();cache={} if receipt_cache is None else receipt_cache
    last=None;scanned=0
    if count==0:
        yield dict(status='NO_DATA',rows=[],selected_count=0,scanned_count=0,truncated=False,excluded_counts={},missing_tables=[])
        return
    while True:
        page=query
        if last is not None:
            page=page.filter(or_(ObservationStandard.timestamp_utc>last[0],and_(ObservationStandard.timestamp_utc==last[0],ObservationStandard.observation_id>last[1])))
        pairs=page.order_by(ObservationStandard.timestamp_utc,ObservationStandard.observation_id).limit(batch_size).all()
        if not pairs: break
        keys=[tuple(getattr(row,k) for k in ('station_id','sensor_id','variable_code','timestamp_utc')) for row,_ in pairs]
        columns=tuple_(ObservationRaw.station_id,ObservationRaw.sensor_id,ObservationRaw.variable_code,ObservationRaw.timestamp_utc)
        raws={tuple(getattr(row,k) for k in ('station_id','sensor_id','variable_code','timestamp_utc')):row
              for row in db.query(ObservationRaw).filter(columns.in_(keys)).all()}
        rows=[];excluded=Counter()
        for observation,binding in pairs:
            try:
                receipt=_receipt(db,binding,cache)
                key=tuple(getattr(observation,k) for k in ('station_id','sensor_id','variable_code','timestamp_utc'))
                rows.append(_registered_row(observation,binding,receipt,raws.get(key),window))
            except (CandidateError,SourceContractError,OSError,ValueError) as exc:
                excluded[getattr(exc,'code',None) or 'SOURCE_AUTHORITY_UNVERIFIED']+=1
        scanned+=len(pairs);last=(pairs[-1][0].timestamp_utc,pairs[-1][0].observation_id)
        yield dict(status='PARTIAL' if excluded else 'AVAILABLE' if rows else 'NO_DATA',rows=rows,
            selected_count=count,scanned_count=len(pairs),truncated=False,excluded_counts=dict(excluded),missing_tables=[])
    if scanned!=count or query.count()!=count: raise CandidateError('REGISTERED_POPULATION_CHANGED_DURING_QUERY')


def verify_cached_authority(db,receipt_cache):
    """Final live ledger/packet/source validation before publishing a census."""
    for sha,item in receipt_cache.items():
        if item.get('receipt') is not None:
            try: verify_approved_receipt(db,item['receipt'],sha)
            except (SourceContractError,OSError,ValueError): raise CandidateError('SOURCE_AUTHORITY_CHANGED_DURING_QUERY') from None


def _definition_snapshot(row):
    return {column.key:_json(getattr(row,column.key)) for column in inspect(QCRuleDefinition).columns}


def verify_definition_cache(db,definition_cache):
    for key,item in definition_cache.items():
        row=db.query(QCRuleDefinition).filter_by(qc_rule_id=key[0],rule_version=key[1]).populate_existing().first()
        if item is None:
            if row is not None: raise CandidateError('RULE_DEFINITION_CHANGED_DURING_QUERY')
        elif row is None or digest(_definition_snapshot(row))!=item['sha256']:
            raise CandidateError('RULE_DEFINITION_CHANGED_DURING_QUERY')


def _rule_result(row, observation, definition, window):
    _,_,cutoff = _window_clocks(window)
    provenance = row.provenance_json if isinstance(row.provenance_json, dict) else {}
    if row.observation_id != observation['observation_id'] or any(getattr(row,k) != observation[k] for k in ('station_id','sensor_id','variable_code')):
        raise CandidateError('RULE_OBSERVATION_SCOPE_MISMATCH')
    if _utc_column(row.timestamp_utc) != _aware(observation['observation_time']): raise CandidateError('RULE_EVENT_CLOCK_MISMATCH')
    if provenance.get('engine_version') != engine.ENGINE_VERSION or provenance.get('event_clock_policy') != 'EXPLICIT_OFFSET_INSTANT':
        raise CandidateError('RULE_FLAG_NAMESPACE_UNVERIFIED')
    if any(provenance.get(k) != v for k,v in engine.implementation_hashes().items()): raise CandidateError('RULE_IMPLEMENTATION_VERSION_UNVERIFIED')
    facts = provenance.get('source_facts') or {}
    if any(facts.get(k) != observation[k] for k in ('physical_sensor_id','sensor_episode_id')): raise CandidateError('RULE_SENSOR_EPISODE_MISMATCH')
    evidence_scope = provenance.get('evidence_scope') or {}
    if any(evidence_scope.get(k) != observation[k] for k in ('station_id','sensor_id','variable_code','unit')): raise CandidateError('RULE_EXACT_SCOPE_UNVERIFIED')
    evidence = facts.get('evidence') or {}
    if evidence.get('sha256') != observation['receipt_sha256'] or evidence.get('locator') != observation['source_row_locator']:
        raise CandidateError('RULE_SOURCE_BINDING_UNVERIFIED')
    if _aware(provenance.get('event_at')) != _aware(observation['observation_time']): raise CandidateError('RULE_EVENT_CLOCK_MISMATCH')
    available = _aware(provenance.get('available_at'))
    if available > cutoff or available != _aware(provenance.get('executed_at_utc')) or available < _aware(observation['available_at']):
        raise CandidateError('RULE_AVAILABILITY_UNVERIFIED')
    config = provenance.get('configuration')
    if not definition or not isinstance(config, dict) or digest(config) != provenance.get('rule_spec_sha256'):
        raise CandidateError('RULE_CONFIGURATION_VERSION_UNVERIFIED')
    expected = dict(definition.threshold_definition or {}, qc_rule_id=definition.qc_rule_id, rule_version=definition.rule_version)
    if config != expected or row.qc_rule_id != config.get('qc_rule_id') or row.rule_version != config.get('rule_version'):
        raise CandidateError('RULE_DEFINITION_CHANGED')
    if not _same_number(row.input_value,observation['value']): raise CandidateError('RULE_INPUT_VALUE_CHANGED')
    if row.observation_id not in provenance.get('input_observation_ids',[]) or not SHA.fullmatch(str(provenance.get('input_window_sha256',''))):
        raise CandidateError('RULE_INPUT_MEMBERSHIP_UNVERIFIED')
    if row.result_flag not in FLAGS or row.evaluation_status not in {'EVALUATED','MISSING','NOT_EVALUATED'}:
        raise CandidateError('RULE_FLAG_UNDEFINED')
    if (row.result_flag == '9') != (row.evaluation_status == 'MISSING') or (row.result_flag == 'NOT_EVALUATED') != (row.evaluation_status == 'NOT_EVALUATED'):
        raise CandidateError('RULE_FLAG_STATUS_CONFLICT')
    return dict(id='qc:'+row.qc_result_id, kind='REGISTERED_QC_CANDIDATE', qc_result_id=row.qc_result_id,
        observation_id=row.observation_id, station_id=row.station_id, item_code=row.variable_code,
        sensor_id=row.sensor_id, variable_code=row.variable_code, observation_time=observation['observation_time'], value=observation['value'],
        flag=row.result_flag, result_flag=row.result_flag, meaning=FLAGS[row.result_flag][0], label=FLAGS[row.result_flag][1],
        priority=FLAGS[row.result_flag][2], rule_id=row.qc_rule_id, rule_name=row.qc_rule_name,
        rule_version=row.rule_version, threshold_value=row.threshold_value, threshold_definition=config.get('parameters'),
        input_value=row.input_value, evaluation_status=row.evaluation_status, reason=row.result_reason,
        available_at=available.isoformat(), executed_at_utc=available.isoformat(), qc_rule_id=row.qc_rule_id,
        rule_type=config.get('kind'), severity=row.result_flag, provenance=provenance, review_status='UNVERIFIED', approved=False)


def registered_rule_results(db, observations, window,*,definition_cache=None):
    rows=[];excluded=Counter();definitions={} if definition_cache is None else definition_cache
    for batch in iter_registered_rule_batches(db,observations,window,definition_cache=definitions):
        rows.extend(batch['rows']);excluded.update(batch['excluded_counts'])
        if len(rows)>MAX_ROWS:
            verify_definition_cache(db,definitions)
            return dict(rows=rows[:MAX_ROWS],excluded_counts=dict(excluded),truncated=True)
    verify_definition_cache(db,definitions)
    return dict(rows=rows,excluded_counts=dict(excluded),truncated=False)


def iter_registered_rule_batches(db, observations, window, *, batch_size=500, definition_cache=None):
    if not 1<=batch_size<=500 or len(observations)>MAX_ROWS: raise CandidateError('INVALID_RULE_BATCH_SIZE')
    if not observations: return dict(rows=[], excluded_counts={}, truncated=False)
    if 'qc_rule_result' not in inspect(db.connection()).get_table_names():
        yield dict(rows=[],excluded_counts={'RULE_TABLE_ABSENT':1},truncated=False)
        return
    by_id={r['observation_id']:r for r in observations};definitions={} if definition_cache is None else definition_cache
    query=db.query(QCRuleResult).filter(QCRuleResult.observation_id.in_(by_id));last=None
    while True:
        page=query if last is None else query.filter(QCRuleResult.qc_result_id>last)
        results=page.order_by(QCRuleResult.qc_result_id).limit(batch_size).all()
        if not results: break
        rows=[];excluded=Counter()
        keys={(r.qc_rule_id,r.rule_version) for r in results}-definitions.keys()
        if keys:
            for key in keys: definitions[key]=None
            for definition in db.query(QCRuleDefinition).filter(tuple_(QCRuleDefinition.qc_rule_id,QCRuleDefinition.rule_version).in_(list(keys))).all():
                snapshot=_definition_snapshot(definition)
                definitions[(definition.qc_rule_id,definition.rule_version)]=dict(definition=SimpleNamespace(**snapshot),sha256=digest(snapshot))
        for row in results:
            item=definitions[(row.qc_rule_id,row.rule_version)]
            try: rows.append(_rule_result(row,by_id[row.observation_id],item['definition'] if item else None,window))
            except CandidateError as exc: excluded[exc.code]+=1
        last=results[-1].qc_result_id
        yield dict(rows=rows,scanned_count=len(results),excluded_counts=dict(excluded),truncated=False)


def priority_queue(rule_results, limit=15):
    """One representative persisted anomaly per observation, BAD then Suspect."""
    if not 1<=limit<=100: raise CandidateError('INVALID_QUEUE_LIMIT')
    grouped={}
    for row in rule_results:
        if row['meaning'] not in {'BAD','SUSPECT','MISSING'}: continue
        key=row['observation_id']; prior=grouped.get(key)
        if prior is None or (row['priority'],row['qc_result_id']) < (prior['priority'],prior['qc_result_id']): grouped[key]=row
    rows=sorted(grouped.values(),key=lambda r:(r['priority'],-_aware(r['observation_time']).timestamp(),r['qc_result_id']))
    return dict(rows=rows[:limit],total=len(rows),limit=limit,ordering='BAD_SUSPECT_MISSING_THEN_OBSERVATION_DESC',population='VERIFIED_PERSISTED_RULE_RESULTS')


def surrounding_packet(rows, center, cutoff, half_window_minutes=120, *, native=False):
    """Keep duplicates and raw gaps. Grid markers are a stated inference only."""
    if not 1<=half_window_minutes<=120: raise CandidateError('INVALID_HALF_WINDOW')
    clock=(lambda v: datetime.fromisoformat(v)) if native else _aware
    target,stop=clock(center),clock(cutoff)
    begin=target-timedelta(minutes=half_window_minutes);end=min(target+timedelta(minutes=half_window_minutes),stop)
    selected=[r for r in rows if begin<=clock(r['observation_time'])<=end]
    selected.sort(key=lambda r:(clock(r['observation_time']),str(r.get('observation_id',r.get('source_row_locator','')))))
    truncated=len(selected)>CHART_LIMIT
    selected=selected[:CHART_LIMIT]
    times=sorted({clock(r['observation_time']) for r in selected})
    deltas=Counter((b-a).total_seconds() for a,b in zip(times,times[1:]) if b>a)
    cadence=None;gaps=[]
    if len(times)>=12 and deltas and not truncated:
        interval,count=deltas.most_common(1)[0]
        if count/sum(deltas.values())>=.8 and interval>0:
            cadence=interval
            for a,b in zip(times,times[1:]):
                slots=(b-a).total_seconds()/interval
                if slots>1 and slots.is_integer() and slots<=CHART_LIMIT:
                    for i in range(1,int(slots)):
                        gaps.append(dict(observation_time=(a+timedelta(seconds=interval*i)).isoformat(),value=None,is_gap=True,
                            actual_value=False,flag=None,reason='INFERRED_OBSERVED_GRID_GAP_NOT_RECEIVE_FLAG'))
                        if len(gaps)>=CHART_LIMIT: break
                if len(gaps)>=CHART_LIMIT: break
    return dict(rows=selected,gaps=gaps,window_start=begin.isoformat(),window_end=end.isoformat(),
        truncated=truncated,gap_markers_truncated=len(gaps)>=CHART_LIMIT,cadence_seconds=cadence,
        cadence_status='INFERRED_FROM_OBSERVED_CLOCKS' if cadence else 'UNVERIFIED',
        interpolation=False,received_time_replaced=False,expected_observation_schedule_verified=False)


def _exact_evidence(metadata, observation, cutoff):
    if metadata.get('observation_id') != observation['observation_id'] or metadata.get('authority_sha256') != observation['authority_sha256']:
        raise CandidateError('EVIDENCE_OBSERVATION_AUTHORITY_MISMATCH')
    scope=metadata.get('scope')
    if not isinstance(scope,dict) or scope != _scope(observation): raise CandidateError('EVIDENCE_EXACT_SCOPE_MISMATCH')
    available,version=(_aware(metadata.get(k)) for k in ('available_at','version_available_at'))
    if version<available or version>cutoff or available>cutoff: raise CandidateError('POST_CUTOFF_EVIDENCE_OR_VERSION')
    return metadata


def stored_ai(predictions, models, observation, window):
    _,_,cutoff=_window_clocks(window);out=[];excluded=Counter()
    by_version={m.model_version:m for m in models}
    for row in predictions:
        try:
            metadata=_payload(row.explanation)
            if metadata.get('schema_version')!='qc-stored-ai-1': raise CandidateError('AI_RESULT_PROVENANCE_UNVERIFIED')
            _exact_evidence(metadata,observation,cutoff)
            if any(getattr(row,k)!=observation[k] for k in ('station_id','sensor_id','variable_code')) or _utc_column(row.timestamp_utc)!=_aware(observation['observation_time']):
                raise CandidateError('AI_RESULT_OBSERVATION_MISMATCH')
            model=by_version.get(row.model_id)
            if not model or metadata.get('model_version')!=model.model_version: raise CandidateError('AI_MODEL_VERSION_UNBOUND')
            metrics=model.metrics_json or {}
            if _aware(metrics.get('available_at'))>cutoff: raise CandidateError('POST_CUTOFF_MODEL')
            if model.training_data_end and _aware(metrics.get('training_data_end_utc'))>cutoff: raise CandidateError('POST_CUTOFF_MODEL_TRAINING')
            if model.target_variable!=observation['variable_code'] or metrics.get('artifact_sha256')!=metadata.get('model_sha256') or not SHA.fullmatch(str(metadata.get('model_sha256',''))):
                raise CandidateError('AI_MODEL_ARTIFACT_OR_VARIABLE_MISMATCH')
            expected=_finite(row.predicted_value)
            residual=None if expected is None else observation['value']-expected
            out.append(dict(id=row.id,model=model.model_name,model_version=model.model_version,model_sha256=metadata['model_sha256'],
                observation_time=observation['observation_time'],predicted_value=expected,residual=residual,residual_basis='ACTUAL_MINUS_STORED_PREDICTION' if residual is not None else None,
                anomaly_score=_finite(row.anomaly_score),confidence=_finite(row.confidence),drift_score=_finite(metadata.get('drift_score')),
                level_shift=_finite(metadata.get('level_shift')),recommended_flag=row.recommended_flag,cause_candidate=row.cause_candidate,
                available_at=metadata['available_at'],version_available_at=metadata['version_available_at'],
                model_status=model.status,deployment_status=model.deployment_status,deployment_stage=model.deployment_stage,
                is_champion=bool(model.is_champion),active_approved_serving=None,
                registry_declares_active_approved=(model.status=='APPROVED' and model.deployment_status=='DEPLOYED' and model.deployment_stage=='PRODUCTION' and bool(model.is_champion)),
                serving_health_status='NOT_PROBED_BY_READONLY_DETAIL',
                registry_declares_production_approved=model.status=='APPROVED',production_approval_verified=False,
                stored_only=True,source_qc_finalized=False))
        except CandidateError as exc: excluded[exc.code]+=1
    return dict(status='AVAILABLE' if out else 'UNVERIFIED' if predictions else 'NOT_EXECUTED' if models else 'NO_MODEL',
        results=out,excluded_counts=dict(excluded),inference_executed=False)


def validate_linked_workflow(db,run,observation,window,*,workflow_cache=None):
    """Existing exact candidate references, aware version and live workflow gate."""
    from app.agents import multi_agent_workflow as workflow
    _,_,cutoff=_window_clocks(window)
    scope=run.payload.get('scope') or {};bundle=run.payload.get('bundle') or {}
    if any(scope.get(k)!=observation[k] for k in ('station_id','sensor_id','variable_code','unit')): return None
    refs=bundle.get('references',[]);needed={'ObservationStandard','SourceObservationBinding'}
    linked={r.get('model') for r in refs if r.get('pk',{}).get('observation_id')==observation['observation_id']}
    if not needed<=linked:
        other={model:{r.get('pk',{}).get('observation_id') for r in refs if r.get('model')==model} for model in needed}
        if not linked and (other['ObservationStandard'] & other['SourceObservationBinding'])-{None}: return None
        raise CandidateError('WORKFLOW_CANDIDATE_REFERENCES_UNVERIFIED')
    if not _aware(scope.get('period_start'))<=_aware(observation['observation_time'])<_aware(scope.get('period_end')): return None
    if scope.get('sensor_episode_id')!=observation['sensor_episode_id']: raise CandidateError('WORKFLOW_SENSOR_EPISODE_UNVERIFIED')
    if _aware(scope.get('as_of'))>cutoff or _aware(run.created_at)>cutoff: raise CandidateError('POST_CUTOFF_WORKFLOW')
    if _aware(run.updated_at)>cutoff: raise CandidateError('POST_CUTOFF_WORKFLOW_REVISION')
    key=(run.workflow_id,run.revision,run.input_sha256,run.recommendation_sha256)
    if workflow_cache is None or key not in workflow_cache:
        workflow._integrity(db,run,current=True)
        if workflow_cache is not None: workflow_cache[key]=run
    return workflow.view(run)


def verify_workflow_cache(db,workflow_cache):
    from app.agents import multi_agent_workflow as workflow
    for key,run in workflow_cache.items():
        if key!=(run.workflow_id,run.revision,run.input_sha256,run.recommendation_sha256): raise CandidateError('WORKFLOW_CHANGED_DURING_QUERY')
        try: workflow._integrity(db,run,current=True)
        except (workflow.WorkflowError,ValueError,OSError): raise CandidateError('WORKFLOW_CHANGED_DURING_QUERY') from None


def registered_review_states(db,observations,window,*,workflow_cache=None):
    """Census of exact linked existing workflows, never final QC counts."""
    from app.agents import multi_agent_workflow as workflow
    if not observations: return dict(rows=[],excluded_counts={},excluded_by_observation={},state='NO_LINKED_WORKFLOWS')
    if 'agent_workflow_run' not in inspect(db.connection()).get_table_names():
        return dict(rows=[],excluded_counts={'WORKFLOW_TABLE_ABSENT':1},
            excluded_by_observation={r['observation_id']:{'WORKFLOW_TABLE_ABSENT':1} for r in observations},state='UNAVAILABLE')
    matched={};ambiguous=set();excluded=Counter();per_observation={};cache={} if workflow_cache is None else workflow_cache
    for runs in _station_workflow_batches(db,{r['station_id'] for r in observations}):
        for run in runs:
            for observation in observations:
                try:
                    result=validate_linked_workflow(db,run,observation,window,workflow_cache=cache)
                    if result:
                        oid=observation['observation_id']
                        if oid in matched: ambiguous.add(oid)
                        else: matched[oid]=dict(observation_id=oid,workflow_id=run.workflow_id,
                            status=run.status,revision=run.revision,available_at=_json(run.updated_at),recommendation_sha256=run.recommendation_sha256,
                            definitive_qc=False,completed_means='WORKFLOW_REPORT_DRAFT_AND_MLOPS_RECOMMENDATION_ONLY')
                except (CandidateError,workflow.WorkflowError,ValueError,KeyError) as exc:
                    reason=getattr(exc,'code','WORKFLOW_UNVERIFIED');excluded[reason]+=1
                    per_observation.setdefault(observation['observation_id'],Counter())[reason]+=1
    if ambiguous:
        excluded['AMBIGUOUS_CANDIDATE_WORKFLOWS']+=len(ambiguous)
        for oid in ambiguous:per_observation.setdefault(oid,Counter())['AMBIGUOUS_CANDIDATE_WORKFLOWS']+=1
    rows=[row for oid,row in matched.items() if oid not in per_observation]
    return dict(rows=rows,excluded_counts=dict(excluded),excluded_by_observation={oid:dict(counts) for oid,counts in per_observation.items()},
        state='PARTIAL' if excluded else 'AVAILABLE' if rows else 'NO_LINKED_WORKFLOWS')


def _station_workflow_batches(db,stations):
    """Same full, bounded keyset population for overview and detail."""
    query=db.query(AgentWorkflowRun).filter(AgentWorkflowRun.payload['scope']['station_id'].as_string().in_(stations))
    last=None
    while True:
        page=query if last is None else query.filter(AgentWorkflowRun.workflow_id>last)
        rows=page.order_by(AgentWorkflowRun.workflow_id).limit(500).all()
        if not rows: return
        yield rows
        last=rows[-1].workflow_id


def workflow_capabilities(db, observation, window, actor=None,*,workflow_cache=None):
    from app.agents import multi_agent_workflow as workflow
    _,_,cutoff=_window_clocks(window);match=None;match_count=0;excluded=Counter();scanned=0
    for runs in _station_workflow_batches(db,{observation['station_id']}):
        scanned+=len(runs)
        for run in runs:
            try:
                if validate_linked_workflow(db,run,observation,window,workflow_cache=workflow_cache):
                    match_count+=1
                    if match is None: match=run
            except (CandidateError,workflow.WorkflowError,ValueError,KeyError) as exc: excluded[getattr(exc,'code','WORKFLOW_UNVERIFIED')]+=1
    if match_count!=1 or excluded:
        status='AMBIGUOUS' if match_count>1 else 'UNVERIFIED' if excluded else 'NO_LINKED_WORKFLOW'
        return dict(status=status,matches=match_count,excluded_counts=dict(excluded),truncated=False,scanned_workflows=scanned),[] ,[]
    run=match;view=workflow.view(run)
    configured=bool(settings.API_IDENTITIES);role=actor.role if isinstance(actor,Actor) else None
    capabilities=[]
    for action,required,allowed_status in (('APPROVED','reviewer',{'PENDING'}),('REJECTED','reviewer',{'PENDING'}),('RESUME','operator',{'APPROVED'}),('CANCEL','operator',{'PENDING','APPROVED'})):
        authorized=role in ({'reviewer','admin'} if required=='reviewer' else {'operator','reviewer','admin'})
        owner=required=='reviewer' or actor is not None and (role in {'reviewer','admin'} or actor.user_id==run.requested_by)
        enabled=configured and authorized and owner and run.status in allowed_status
        suffix='decision' if action in {'APPROVED','REJECTED'} else action.lower()
        body=dict(request_key=f'qc-review-{run.workflow_id}-{run.revision}-{action}-{run.recommendation_sha256[:16]}',expected_recommendation_sha256=run.recommendation_sha256,expected_revision=run.revision,comment='')
        if suffix=='decision': body['decision']=action
        capabilities.append(dict(action=action,enabled=enabled,endpoint=f'/api/agents/workflows/{run.workflow_id}/{suffix}',method='POST',
            body_template=body,role_requirement=required,reason=None if enabled else 'OPERATOR_AUTHENTICATION_NOT_CONFIGURED' if not configured else 'AUTHENTICATED_ROLE_OWNER_AND_WORKFLOW_STATE_REQUIRED',
            definitive_qc=False,source_approval_granted=False))
    history=[]
    transitions=db.query(AgentWorkflowTransition).filter_by(workflow_id=run.workflow_id).order_by(AgentWorkflowTransition.revision).limit(101).all()
    for transition in transitions[:100]:
        try:
            if _aware(transition.created_at)<=cutoff:
                history.append(_json(transition.record)|{'created_at':_json(transition.created_at)})
        except CandidateError: excluded['WORKFLOW_TRANSITION_CLOCK_UNVERIFIED']+=1
    return view|{'excluded_counts':dict(excluded),'history_truncated':len(transitions)>100,'scanned_workflows':scanned,'truncated':False},capabilities,history


def _linked_evidence(db, observation, window):
    _,_,cutoff=_window_clocks(window);operations=[];rag=[];inspections=[];equipment=[];links=[];excluded=Counter()
    operation_rows=db.query(OperationLog).filter_by(station_id=observation['station_id'],sensor_id=observation['sensor_id']).order_by(OperationLog.id.desc()).limit(101).all()
    document_rows=db.query(DocumentIndex).filter_by(related_station_id=observation['station_id'],related_sensor_id=observation['sensor_id'],related_variable_code=observation['variable_code']).order_by(DocumentIndex.id.desc()).limit(101).all()
    def check_record(row,metadata,excluded_fields=()):
        content=record_content_sha256(row,excluded_fields=excluded_fields)
        if metadata.get('record_sha256')!=content: raise CandidateError('LINKED_RECORD_CONTENT_HASH_MISMATCH')
        _exact_evidence(metadata,observation,cutoff)
        event=_aware(metadata.get('event_at'))
        if event>cutoff or event>_aware(metadata['available_at']): raise CandidateError('POST_CUTOFF_OR_UNAVAILABLE_EVIDENCE_EVENT')
        if any(not _aware(metadata.get(first))<=_aware(observation['observation_time'])<_aware(metadata.get(last)) for first,last in [('period_start','period_end')]):
            raise CandidateError('EVIDENCE_PERIOD_NOT_APPLICABLE')
        return metadata
    def accept_links(metadata,source_kind,source_id):
        pending_links=[];pending_equipment=[]
        for link in metadata.get('inspection_refs',[]):
            if not isinstance(link,dict): raise CandidateError('INSPECTION_REFERENCE_INVALID')
            pending_links.append(dict(link,source_kind=source_kind,source_id=source_id))
        event=metadata.get('equipment_event')
        if event is not None:
            if not isinstance(event,dict) or event.get('kind') not in {'INSTALLATION','REPLACEMENT','CALIBRATION'}:
                raise CandidateError('EQUIPMENT_EVENT_KIND_UNDEFINED')
            when=_aware(event.get('event_at'))
            proof=observation['source_proof']
            if (event.get('physical_sensor_id')!=observation['physical_sensor_id'] or event.get('sensor_episode_id')!=observation['sensor_episode_id']
                    or not _aware(proof['effective_start'])<=when<_aware(proof['effective_end']) or when>cutoff
                    or when>_aware(metadata['available_at'])): raise CandidateError('EQUIPMENT_EVENT_EPISODE_OR_CLOCK_MISMATCH')
            pending_equipment.append(dict(kind=event['kind'],event_at=event['event_at'],physical_sensor_id=event['physical_sensor_id'],
                sensor_episode_id=event['sensor_episode_id'],source_kind=source_kind,source_id=source_id,
                record_sha256=metadata['record_sha256'],available_at=metadata['available_at'],version_available_at=metadata['version_available_at'],approved=False))
        links.extend(pending_links);equipment.extend(pending_equipment)
    for row in operation_rows[:100]:
        try:
            metadata=check_record(row,_payload(row.event_detail),('event_detail',))
            accept_links(metadata,'OPERATION_LOG',str(row.id))
            operations.append(dict(id=row.id,event_time=metadata['event_at'],event_type=row.event_type,action_taken=row.action_taken,available_at=metadata['available_at'],metadata=metadata,
                version_available_at=metadata['version_available_at'],record_sha256=metadata['record_sha256'],authority='EXPLICIT_STORED_VERSION_LINK',approved=False))
        except CandidateError as exc: excluded[exc.code]+=1
    for row in document_rows[:100]:
        try:
            metadata=check_record(row,row.metadata_json or {},('metadata_json',))
            if not SHA.fullmatch(str(metadata.get('source_sha256',''))): raise CandidateError('DOCUMENT_SOURCE_SHA_REQUIRED')
            accept_links(metadata,'DOCUMENT_CHUNK',row.chunk_id)
            rag.append(dict(chunk_id=row.chunk_id,title=row.document_title,page=row.page_no,text=row.chunk_text,
                source_sha256=metadata['source_sha256'],available_at=metadata['available_at'],version_available_at=metadata['version_available_at'],
                record_sha256=metadata['record_sha256'],retrieval='STORED_EXACT_SCOPE_DOCUMENT_NOT_NEW_SEARCH',approved=False))
        except CandidateError as exc: excluded[exc.code]+=1
    refs={str(link.get('inspection_id')) for link in links if link.get('inspection_id')}
    if refs:
        actual={r.inspection_id:r for r in db.query(DailyInspectionReport).filter(DailyInspectionReport.inspection_id.in_(refs)).all()}
        seen=set()
        for link in links:
            try:
                row=actual.get(link.get('inspection_id'))
                if not row or row.station_id!=observation['station_id'] or row.sensor_id!=observation['sensor_id']: raise CandidateError('INSPECTION_RECORD_OR_SENSOR_MISMATCH')
                check_record(row,link)
                key=(row.inspection_id,link['record_sha256'])
                if key in seen: continue
                seen.add(key)
                inspections.append(dict(inspection_id=row.inspection_id,report_id=row.report_id,event_time=link['event_at'],
                    equipment_status=row.equipment_status,communication_status=row.communication_status,power_status=row.power_status,
                    issue_found=row.issue_found,issue_detail=row.issue_detail,action_taken=row.action_taken,
                    available_at=link['available_at'],version_available_at=link['version_available_at'],record_sha256=link['record_sha256'],
                    source_kind=link['source_kind'],source_id=link['source_id'],authority='EXPLICIT_STORED_VERSION_LINK',approved=False))
            except CandidateError as exc: excluded[exc.code]+=1
    held_inspections=db.query(DailyInspectionReport).filter_by(station_id=observation['station_id'],sensor_id=observation['sensor_id']).count()
    if len(operation_rows)>100 or len(document_rows)>100: excluded['EVIDENCE_LOOKUP_TRUNCATED']+=1
    return dict(operations=dict(status='AVAILABLE' if operations else 'UNVERIFIED' if operation_rows else 'NO_EVIDENCE',rows=operations,truncated=len(operation_rows)>100),
        inspection=dict(status='AVAILABLE' if inspections else 'UNVERIFIED' if held_inspections else 'NO_EVIDENCE',rows=inspections,
            held_matching_records=held_inspections,reason=None if inspections else 'NO_EXACT_CONTENT_HASH_AND_EXPLICIT_VERSION_LINK'),
        rag=dict(status='AVAILABLE' if rag else 'UNVERIFIED' if document_rows else 'NO_EVIDENCE',rows=rag,truncated=len(document_rows)>100),
        equipment_events=equipment,excluded_counts=dict(excluded))


def record_content_sha256(row,*,excluded_fields=()):
    """Hash stored bytes/fields; never assign a timezone to generic DB dates.

    Link-bearing JSON/text columns exclude themselves to avoid a self-hash.
    Inspection content is fully hashed because its link lives in another row.
    """
    return digest({column.key:_json(getattr(row,column.key)) for column in inspect(type(row)).columns if column.key not in excluded_fields})


def equipment_epoch(observation,evidence):
    proof=observation['source_proof'];events=evidence.get('equipment_events',[])
    latest={}
    for event in events:
        kind=event['kind']
        if kind not in latest or _aware(event['event_at'])>_aware(latest[kind]['event_at']): latest[kind]=event
    return dict(status='EXPLICIT_LINKED_EQUIPMENT_EVENTS' if events else 'APPROVED_SOURCE_EPISODE_ONLY',
        physical_sensor_id=observation['physical_sensor_id'],sensor_id=observation['sensor_id'],sensor_episode_id=observation['sensor_episode_id'],
        effective_start=proof['effective_start'],effective_end=proof['effective_end'],
        install_date=latest.get('INSTALLATION',{}).get('event_at'),replacement_date=latest.get('REPLACEMENT',{}).get('event_at'),
        calibration_date=latest.get('CALIBRATION',{}).get('event_at'),events=events,
        reason=None if events else 'CURRENT_SENSOR_METADATA_IS_NOT_HISTORICAL_INSTALL_CALIBRATION_EVIDENCE',approved_equipment_history=False)


def _point(row, rules=()):
    result={key:value for key,value in row.items() if key!='source_proof'}
    ordered=sorted(rules,key=lambda r:(r['priority'],r['qc_result_id']))
    result['flag']=ordered[0]['flag'] if ordered else None
    result['qc']=dict(status='PERSISTED_RULE_RESULTS' if ordered else 'NOT_EXECUTED',results=ordered)
    delays=[r for r in ordered if r['rule_type']=='DE' and r['evaluation_status']=='EVALUATED']
    if delays:
        result['delay_flag']=delays[0]['flag'];result['is_late']=delays[0]['meaning'] in {'BAD','SUSPECT'}
        result['delay_policy']=dict(rule_id=delays[0]['rule_id'],rule_version=delays[0]['rule_version'],threshold_seconds=delays[0]['threshold_value'])
    return result


def registered_detail(db, candidate_id, window, station='', item='', half_window_minutes=120, actor=None):
    if not re.fullmatch(r'qc:[A-Za-z0-9_-]{1,128}',candidate_id): raise CandidateError('INVALID_CANDIDATE_ID')
    row=db.get(QCRuleResult,candidate_id[3:])
    if not row: raise CandidateError('CANDIDATE_NOT_FOUND')
    if station and station!=row.station_id or item and item!=row.variable_code: raise CandidateError('CANDIDATE_SCOPE_MISMATCH')
    receipt_cache={};definition_cache={};workflow_cache={}
    target_population=registered_rows(db,window,row.station_id,row.variable_code,observation_id=row.observation_id,receipt_cache=receipt_cache)
    observation=next(iter(target_population['rows']),None)
    if not observation: raise CandidateError('CANDIDATE_SOURCE_AUTHORITY_UNAVAILABLE')
    results=registered_rule_results(db,[observation],window,definition_cache=definition_cache)
    if not any(r['id']==candidate_id for r in results['rows']): raise CandidateError('CANDIDATE_RULE_AUTHORITY_UNAVAILABLE')
    center=_aware(observation['observation_time']);stop=_aware(window['as_of'])
    chart_window=window|dict(start=(center-timedelta(minutes=half_window_minutes)).isoformat(),end=min(center+timedelta(minutes=half_window_minutes),stop).isoformat())
    population=registered_rows(db,chart_window,row.station_id,row.variable_code,receipt_cache=receipt_cache)
    surrounding=[r for r in population['rows'] if _scope(r)==_scope(observation) and r['source_group']==observation['source_group']]
    surrounding_rules=registered_rule_results(db,surrounding,chart_window,definition_cache=definition_cache)
    rules_by_id={}
    for result in surrounding_rules['rows']: rules_by_id.setdefault(result['observation_id'],[]).append(result)
    predictions=db.query(AIPredictionResult).filter_by(station_id=row.station_id,sensor_id=row.sensor_id,variable_code=row.variable_code,timestamp_utc=row.timestamp_utc).order_by(AIPredictionResult.id).limit(101).all()
    models=db.query(ModelRegistry).filter(ModelRegistry.model_version.in_([p.model_id for p in predictions])).all() if predictions else db.query(ModelRegistry).filter_by(target_variable=row.variable_code).limit(101).all()
    work,capabilities,history=workflow_capabilities(db,observation,window,actor,workflow_cache=workflow_cache)
    proof=observation['source_proof']
    evidence=_linked_evidence(db,observation,window)
    packet=dict(schema_version=SCHEMA,kind='REGISTERED_QC_CANDIDATE',id=candidate_id,source='REGISTERED',snapshot=None,
        window=window,scope=dict(station=station,item=item,candidate_scope=_scope(observation)),observation=_point(observation,results['rows']),
        surrounding_timeseries=surrounding_packet([_point(r,rules_by_id.get(r['observation_id'],())) for r in surrounding],observation['observation_time'],window['as_of'],half_window_minutes),
        rule_results=results,ai=stored_ai(predictions,models,observation,window),
        equipment_epoch=equipment_epoch(observation,evidence),
        evidence=evidence,workflow=work,capabilities=capabilities,review_history=history,
        flag_catalog=flag_catalog(),provenance=dict(mutations=[],training_executed=False,inference_executed=False,
            final_qc_written=False,source_binding_required=True,registered_population=population|{'rows':None}))
    verify_cached_authority(db,receipt_cache);verify_definition_cache(db,definition_cache);verify_workflow_cache(db,workflow_cache)
    packet['result_sha256']=digest(packet)
    return packet


def archive_candidate_id(row):
    sha=row.get('parquet_sha256');number=row.get('file_row_number')
    if not SHA.fullmatch(str(sha)) or type(number) is not int or number<0: raise CandidateError('ARCHIVE_ROW_LOCATOR_REQUIRED')
    return f'archive:{sha}:{number}'


def archive_detail(db, candidate_id, window, snapshot, station='', item='', half_window_minutes=120):
    """Exact immutable file/row locator; bounded actual source rows only."""
    from app.services import lake_browser as lake, observation_asof as dated
    from app.services import qc_workspace as workspace
    from app.services.native_month_metrics import quote
    match=re.fullmatch(r'archive:([0-9a-f]{64}):(0|[1-9]\d{0,11})',candidate_id)
    if not match: raise CandidateError('INVALID_ARCHIVE_CANDIDATE_ID')
    if not 1<=half_window_minutes<=120: raise CandidateError('INVALID_HALF_WINDOW')
    if window.get('clock_basis')!='UNAPPROVED_NATIVE_SOURCE_CLOCK': raise CandidateError('ARCHIVE_NATIVE_CLOCK_REQUIRED')
    for key in ('start','end','as_of'):
        stamp=datetime.fromisoformat(window[key])
        if stamp.tzinfo is not None: raise CandidateError('ARCHIVE_NATIVE_CLOCK_REQUIRED')
    view=lake.context()[0]
    if not snapshot or view.name!=snapshot: raise CandidateError('ARCHIVE_SNAPSHOT_CHANGED')
    source=window['source'];scope=dict(source=source,from_month=window['start'][:7],to_month=window['end'][:7])
    files=workspace._files(view,scope);targets=[r for r in files if r['parquet_sha256']==match[1]]
    if len(targets)!=1: raise CandidateError('ARCHIVE_SOURCE_FILE_NOT_UNIQUE')
    target=targets[0]
    def normalize(c,paths):
        c.read_parquet(paths,hive_partitioning=False,filename=True,file_row_number=True,union_by_name=True).create_view('qc_archive_files')
        columns={r[0] for r in c.execute('DESCRIBE qc_archive_files').fetchall()}
        def col(name): return quote(name) if name in columns else 'NULL::VARCHAR'
        if source=='GD_OBS_ST_MONTHLY':
            projection='trim(station_raw) station_code,trim(item_raw) item_code,station_raw station_literal,item_raw item_literal,time_raw observation_time,value_raw,qc_raw source_qc_raw,mq_raw source_mqc_raw,n1_aqc_raw source_n1_aqc_raw,NULL::VARCHAR depth_step,NULL::VARCHAR depth_from,NULL::VARCHAR depth_to'
            predicate=" WHERE record_class='OBSERVATION_SHAPED_UNVALIDATED'"
        else:
            if 'FROM_DEPTH' in columns and 'FR_DEPTH' in columns: raise CandidateError('SOURCE_DEPTH_ALIAS_CONFLICT')
            depth_from='FROM_DEPTH' if 'FROM_DEPTH' in columns else 'FR_DEPTH'
            projection='trim(OBS_POST_ID) station_code,trim(OBS_ITEM_CODE) item_code,OBS_POST_ID station_literal,OBS_ITEM_CODE item_literal,OBS_TIME observation_time,OBS_VALUE value_raw,'+','.join(col(name)+' '+alias for name,alias in (
                ('QC_FLAG','source_qc_raw'),('MQC_FLAG','source_mqc_raw'),('N1_AQC_FLAG','source_n1_aqc_raw'),('WATER_STEP','depth_step'),(depth_from,'depth_from'),('TO_DEPTH','depth_to')))
            predicate=''
        c.execute('CREATE VIEW qc_archive_normalized AS SELECT '+projection+',filename,file_row_number FROM qc_archive_files'+predicate)
    with lake.connection() as c:
        normalize(c,[target['parquet_path']])
        raw=lake.records(c.execute('SELECT * FROM qc_archive_normalized WHERE file_row_number=?',[int(match[2])]))
    if len(raw)!=1: raise CandidateError('ARCHIVE_ROW_NOT_FOUND')
    raw=raw[0];clock=str(raw['observation_time'])
    if not re.fullmatch(dated.NATIVE_PATTERN,clock): raise CandidateError('ARCHIVE_ROW_CLOCK_INVALID')
    if not datetime.fromisoformat(window['start'])<=datetime.fromisoformat(clock)<=datetime.fromisoformat(window['end']): raise CandidateError('ARCHIVE_ROW_OUTSIDE_WINDOW')
    if station and raw['station_code']!=station or item and raw['item_code']!=item: raise CandidateError('CANDIDATE_SCOPE_MISMATCH')
    center=datetime.fromisoformat(clock);begin=center-timedelta(minutes=half_window_minutes);end=min(center+timedelta(minutes=half_window_minutes),datetime.fromisoformat(window['as_of']))
    with lake.connection() as c:
        normalize(c,[r['parquet_path'] for r in files])
        where='regexp_full_match(CAST(observation_time AS VARCHAR),?) AND try_cast(observation_time AS TIMESTAMP)>=?::TIMESTAMP AND try_cast(observation_time AS TIMESTAMP)<=?::TIMESTAMP AND station_code=? AND item_code=?'
        args=[dated.NATIVE_PATTERN,str(begin),str(end),raw['station_code'],raw['item_code']]
        for field in ('depth_step','depth_from','depth_to'):
            where+=' AND '+field+' IS NOT DISTINCT FROM ?';args.append(raw[field])
        neighbors=lake.records(c.execute('SELECT * FROM qc_archive_normalized WHERE '+where+' ORDER BY try_cast(observation_time AS TIMESTAMP),filename,file_row_number LIMIT ?',args+[CHART_LIMIT+1]))
    assets={str(Path(r['parquet_path']).resolve()):r for r in files}
    def present(row):
        row=dict(row);asset=assets[str(Path(row.pop('filename')).resolve())]
        value=_finite(row['value_raw']);row.update(observation_time=str(row['observation_time']),value=value,unit=None,received_time=None,
            delay_minutes=None,delay_flag='UNKNOWN',late_history=[],is_late=None,is_gap=False,actual_value=True,
            source_sha256=asset['source_sha256'],parquet_sha256=asset['parquet_sha256'],source_row_locator='file_row_number='+str(row['file_row_number']),
            physical_sensor_id=None,sensor_episode_id=None,available_at=None,source_qc_interpreted=False,flag=None)
        return row
    observation=present(raw)
    for asset in files:
        path=Path(asset['parquet_path']);stat=path.stat()
        lake.verify_file(str(path),stat.st_mtime_ns,stat.st_size,asset['parquet_sha256'])
    if lake.context()[0]!=view: raise CandidateError('ARCHIVE_SNAPSHOT_CHANGED')
    packet=dict(schema_version=SCHEMA,kind='ARCHIVE_RAW_SAMPLE',id=candidate_id,source=source,snapshot=snapshot,window=window,
        scope=dict(station=station,item=item,candidate_scope=dict(station_code=observation['station_code'],item_code=observation['item_code'],
            depth_step=observation['depth_step'],depth_from=observation['depth_from'],depth_to=observation['depth_to'])),observation=observation,
        surrounding_timeseries=surrounding_packet([present(r) for r in neighbors],clock,window['as_of'],half_window_minutes,native=True),
        rule_results=dict(rows=[],status='NOT_EXECUTED',reason='NO_APPROVED_SOURCE_BINDING'),
        ai=dict(status='NO_MODEL',results=[],inference_executed=False,reason='NO_MODEL_BOUND_TO_THIS_ARCHIVE_SOURCE_CLOCK_AND_CUTOFF'),
        equipment_epoch=dict(status='UNVERIFIED',physical_sensor_id=None,sensor_episode_id=None),
        evidence={k:dict(status='NO_LINKED_EVIDENCE',rows=[]) for k in ('operations','inspection','rag')},
        workflow=dict(status='NO_LINKED_WORKFLOW'),review_history=[],capabilities=[],flag_catalog=flag_catalog(),
        provenance=dict(storage='PARQUET',mutations=[],approved=False,historical_availability_asserted=False,timezone=None,
            source_files=[dict(file=Path(r['parquet_path']).name,parquet_sha256=r['parquet_sha256'],source_sha256=r['source_sha256']) for r in files],
            inference_executed=False,final_qc_written=False,receipt_unknown=True))
    packet['result_sha256']=digest(packet)
    return packet
