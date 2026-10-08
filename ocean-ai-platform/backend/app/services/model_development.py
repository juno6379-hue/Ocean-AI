"""Read-only task/input inventory and reviewable fixed-policy construction.

Raw literal availability is distinct from physical task readiness. Only live
source, dataset and policy authorities can make a production input ready.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
from app.ml.adapter_registry import adapter_coverage
from app.ml.comparison_runner import ComparisonBlocked, DatabaseAuthority, preflight, read_json, reject_reparse, digest
from app.ml.serving import runtime_root
from app.ml.protocols import validate_protocol
from app.models.domain import DatasetRegistry
from app.models.source_contracts import SourceContractDecision
from app.services.source_contract_snapshot import read_bounded, source_roots

DIAGNOSTIC_ROOT=Path('D:/AI_Observation/outputs/monthly-report-matching/202607/metric-enrichment')
# These are discovery hints, never unit/variable/sensor mapping approval.
RAW_ITEM_HINTS={
    'air_pressure':['AIR_PRES'],'air_temperature':['AIR_TEMP'],'water_temperature':['WATER_TEMP'],
    'salinity':['SALINITY'],'wind_speed':['WIND_SPEED'],'wind_direction':['WIND_DIRECT'],
    'current_speed':['CURRENT_SPEED'],'current_direction':['CURRENT_DIRECT'],
    'wave_height':['SIGNIFI_WAVE_HEIGHT','MAX_WAVE_HEIGHT'],
    'wave_period':['SIGNIFI_WAVE_PERIOD','MAX_WAVE_PERIOD'],'wave_direction':['WAVE_DIRECT'],
    'tide':['TIDE_LEVEL_MIROS','TIDE_LEVEL_OTT','TIDE_LEVEL_VEGA','TIDE_LEVEL_WLS','TIDE_PRES','SEA_LEVEL'],
}


def manifest_catalog(root=None):
    root=runtime_root()/'requests' if root is None else Path(root)
    reject_reparse(root)
    if not root.exists():return {'state':'NO_REQUESTS','manifests':[],'mutation_performed':False}
    result=[]
    for path in sorted(root.glob('*.json'))[:200]:
        try:
            body,sha=read_json(path)
            if not isinstance(body,dict) or body.get('schema_version') not in {'scalar-forecast-comparison-1','typed-model-comparison-2'}:
                raise ComparisonBlocked('COMPARISON_MANIFEST_SCHEMA_REQUIRED')
            result.append({'path':str(path.resolve()),'name':path.name,'sha256':sha,
                           'domain':body.get('domain'),'item_id':body.get('item_id'),'task':body.get('task'),
                           'target_variable':body.get('target_variable'),'unit':body.get('unit'),
                           'splits':body.get('splits'),'status':'PREFLIGHT_REQUIRED'})
        except (OSError,ValueError) as exc:
            result.append({'name':path.name,'path':str(path.absolute()),'status':'INVALID',
                           'blocker':getattr(exc,'code','REQUEST_NOT_READABLE')})
    return {'state':'AVAILABLE' if result else 'NO_REQUESTS','manifests':result,
            'limit':200,'mutation_performed':False,'catalog_is_not_approval':True}


def inspect_manifest(db,path,snapshot_root,expected_sha=None):
    reject_reparse(path)
    path=Path(path).resolve()
    if not path.is_relative_to(runtime_root()/'requests'):raise ComparisonBlocked('MLOPS_INPUT_OUTSIDE_CONFIGURED_ROOT')
    body,actual=read_json(path)
    if expected_sha and actual!=expected_sha:raise ComparisonBlocked('REVIEWED_MANIFEST_CHANGED')
    if not isinstance(body,dict) or body.get('schema_version') not in {'scalar-forecast-comparison-1','typed-model-comparison-2'}:
        raise ComparisonBlocked('COMPARISON_MANIFEST_SCHEMA_REQUIRED')
    try:
        with db.no_autoflush:prepared=preflight(path,DatabaseAuthority(db,snapshot_root))
        return {'status':'READY','training_eligible':True,'manifest_path':str(path),'manifest_sha256':actual,
                'snapshot_hashes':prepared['snapshot_hashes'],'origin_membership_sha256':prepared['origin_membership_sha256'],
                'coverage':prepared['coverage'],'protocol_hashes':{k:v['sha256'] for k,v in prepared['protocols'].items()},
                'training_started':False,'model_registered':False,'mutation_performed':False}
    except ComparisonBlocked as exc:
        return {'status':'BLOCKED','training_eligible':False,'manifest_path':str(path),'manifest_sha256':actual,
                'blockers':[{'code':exc.code,'detail':exc.detail}],'training_started':False,
                'model_registered':False,'mutation_performed':False}


def create_comparison_manifest(db,dataset_ids,snapshot_root):
    if not isinstance(dataset_ids,dict) or set(dataset_ids)!={'TRAIN','VALIDATION','TEST'} or len(set(dataset_ids.values()))!=3:
        raise ComparisonBlocked('THREE_EXPLICIT_DATASET_IDS_REQUIRED')
    authority=DatabaseAuthority(db,snapshot_root);references={};policies=None
    for split,did in dataset_ids.items():
        row=db.get(DatasetRegistry,did)
        if row is None:raise ComparisonBlocked('APPROVED_DATASET_NOT_FOUND',str(did))
        ref={'dataset_id':did,'sha256':row.data_hash}
        snapshot=authority.snapshot(ref,split)
        current=snapshot['_protocols']
        if policies is not None and {r:p['sha256'] for r,p in policies.items()}!={r:p['sha256'] for r,p in current.items()}:
            raise ComparisonBlocked('SPLIT_PROTOCOL_DEPENDENCIES_DIFFER')
        policies=current;references[split]=ref
    evaluation=policies['EVALUATION_PROTOCOL']['body']
    manifest={k:copy.deepcopy(evaluation[k]) for k in ('domain','item_id','task','quantity_kind','target_variable','unit',
                'feature_ids','horizon_seconds','lookback_seconds')}
    manifest.update(schema_version='typed-model-comparison-2',splits=references,
                    locked_holdout_sha256=references['TEST']['sha256'],
                    refit_train_validation=evaluation['preprocessing_fit']=='TRAIN_VALIDATION_REFIT',
                    acceptance_criteria_status='NOT_DEFINED')
    if evaluation['task']=='FORECASTING':manifest['ridge_alphas']=evaluation['ridge_alphas']
    else:manifest['normal_quantiles']=evaluation['normal_quantiles']
    # The legacy report field remains NOT_DEFINED; worker acceptance is evaluated
    # separately against the real frozen ACCEPTANCE_POLICY, never this string.
    from app.ml.protocols import canonical_bytes
    raw=canonical_bytes(manifest);sha=hashlib.sha256(raw).hexdigest()
    root=runtime_root()/'requests';reject_reparse(root);root.mkdir(parents=True,exist_ok=True)
    path=root/(sha+'.json')
    if path.exists():
        if path.read_bytes()!=raw:raise ComparisonBlocked('IMMUTABLE_COMPARISON_REQUEST_CHANGED')
    else:
        from app.services.source_contract_snapshot import immutable_copy
        immutable_copy(root,sha,raw)
        try:os.link(root/'dependencies'/(sha+'.json'),path)
        except FileExistsError:
            if path.read_bytes()!=raw:raise ComparisonBlocked('IMMUTABLE_COMPARISON_REQUEST_CHANGED')
    review=inspect_manifest(db,path,snapshot_root,sha)
    return {**review,'manifest_created':True,'manifest_body':manifest,'mutation_performed':True,
            'database_mutation_performed':False,
            'queue_created':False,'approved_source_and_dataset_authorities_required':True}


def build_policy_bundle(db,selection):
    """Require explicit IDs/periods/candidates; never invent a ratio split."""
    allowed={r['domain']+'|'+r['item_id']+'|'+r['runtime_task']:r for r in adapter_coverage()['rows']}
    key='|'.join(selection.get(k,'') for k in ('domain','item_id','task'))
    if key not in allowed:raise ComparisonBlocked('TASK_DOMAIN_TYPED_ADAPTER_CONTRACT_MISMATCH')
    coverage=allowed[key]
    dataset_ids=selection.get('dataset_ids')
    if not isinstance(dataset_ids,dict) or set(dataset_ids)!={'TRAIN','VALIDATION','TEST'} or len(set(dataset_ids.values()))!=3:
        raise ComparisonBlocked('THREE_EXPLICIT_DATASET_IDS_REQUIRED')
    periods={};members={};snapshots={}
    from app.core.config import settings
    for split,did in dataset_ids.items():
        dataset=db.get(DatasetRegistry,did)
        if dataset is None or dataset.dataset_split!=split or not dataset.data_hash:raise ComparisonBlocked('BUILT_FIXED_DATASET_REQUIRED',str(did))
        body,sha=read_json(Path(settings.DATASET_SNAPSHOT_DIR)/(dataset.data_hash+'.json'))
        if not isinstance(body,dict):raise ComparisonBlocked('FIXED_SNAPSHOT_OBJECT_REQUIRED',str(did))
        if sha!=dataset.data_hash or body.get('dataset_id')!=did or body.get('split')!=split:
            raise ComparisonBlocked('FIXED_SNAPSHOT_REFERENCE_MISMATCH',str(did))
        # Both legacy and v2 can supply a draft membership proposal; a draft
        # policy does not approve either and does not make it a training input.
        records=body.get('records')
        if not isinstance(records,list) or not 1<=len(records)<=250000 or any(
            not isinstance(r,dict) or not isinstance(r.get('id'),str) or not r['id'] for r in records):
            raise ComparisonBlocked('FIXED_MEMBERSHIP_REQUIRED',str(did))
        if len({r['id'] for r in records})!=len(records):raise ComparisonBlocked('FIXED_MEMBERSHIP_DUPLICATE_ID',str(did))
        members[split]=digest(sorted(r['id'] for r in records))
        def utc(value):
            from datetime import timezone
            return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.astimezone(timezone.utc).isoformat()
        periods[split]={'start':utc(dataset.period_start),'end':utc(dataset.period_end)}
        snapshots[split]={'dataset_id':did,'sha256':sha}
    base={k:selection[k] for k in ('domain','item_id','task','target_variable','unit')}
    base.update(schema_version='ocean-model-protocol-1',status='DRAFT',quantity_kind=coverage['quantity_kind'],
                protocol_id=selection['protocol_id'],version=selection['version'])
    strategy=selection['split_strategy']
    groups=['EVENT','SOURCE_RECORD','DOCUMENT_FAMILY']
    if strategy!='temporal_with_purge':groups.append('SENSOR_EPISODE')
    if strategy=='station_holdout':groups.append('STATION')
    split=dict(base,role='SPLIT_PROTOCOL',dataset_ids=dataset_ids,periods=periods,member_ids_sha256=members,
               split_strategy=strategy,disjoint_groups=groups,embargo_seconds=selection['embargo_seconds'],holdout_locked=True)
    evaluation=dict(base,role='EVALUATION_PROTOCOL',feature_ids=selection['feature_ids'],
                    test_pair_policy='ALL_APPROVED_COMMON_ORIGINS',preprocessing_fit='TRAIN_ONLY',
                    horizon_seconds=selection['horizon_seconds'],lookback_seconds=selection['lookback_seconds'],
                    worker_policy={'max_attempts':1,'lease_seconds':300})
    if base['task']=='FORECASTING':evaluation['ridge_alphas']=selection['ridge_alphas']
    else:
        evaluation.update(normal_quantiles=selection['normal_quantiles'],positive_labels=['BAD'],
                          zero_mad_policy='UNIT_SCALE_ONE_EXPLICIT_ENGINEERING_BASELINE')
        if base['task']=='QUALITY_REVIEW':evaluation['human_label_policy']='PRESERVE_ALL_QC_LABELS_BINARY_SCORE_ONLY_NORMAL_BAD'
    required=['min_test_samples','max_local_p95_ms','min_mae_improvement_fraction','max_rmse_regression_fraction'] if base['task']=='FORECASTING' else ['min_test_samples','max_local_p95_ms','min_f1','max_false_positive_rate','max_false_negative_rate']
    if base['task']=='QUALITY_REVIEW':required+=['min_guide_rule_coverage','min_human_qc_agreement','max_false_good_rate']
    supplied=selection.get('limits',{})
    if set(supplied)-set(required):raise ComparisonBlocked('ACCEPTANCE_LIMIT_KEYS_INVALID')
    acceptance=dict(base,role='ACCEPTANCE_POLICY',limits={k:supplied.get(k) for k in required},
                    cost_policy=selection.get('cost_policy','REQUIRES_MEASURED_COST'))
    protocols={b['role']:b for b in (split,evaluation,acceptance)}
    from app.ml.protocols import canonical_bytes
    for role,body in protocols.items():validate_protocol(body,role)
    return {'schema_version':'model-policy-review-bundle-1','status':'DRAFT','approved':False,
            'authority':'ENGINEERING_PROPOSAL_NOT_GUIDE_OR_USER_APPROVAL','snapshots':snapshots,
            'protocols':{r:{'body':b,'sha256':hashlib.sha256(canonical_bytes(b)).hexdigest()} for r,b in protocols.items()},
            'acceptance_criteria_status':'NOT_DEFINED' if any(v is None for v in acceptance['limits'].values()) else 'PROPOSED_UNAPPROVED',
            'mutation_performed':False,'training_eligible':False}


def task_readiness(db,diagnostic_root=None):
    root=DIAGNOSTIC_ROOT if diagnostic_root is None else Path(diagnostic_root)
    raw_channels=[];input_status='UNAVAILABLE';diagnostic_sha=None;source_manifest_sha=None
    diagnostic_issues=[]
    try:
        doc,_,diagnostic_sha=read_bounded(root/'diagnostic-channel-metrics.json',[root])
        manifest,_,source_manifest_sha=read_bounded(root/'source-file-manifest.json',[root])
        if not isinstance(doc,dict) or not isinstance(manifest,dict):
            raise ComparisonBlocked('RAW_DIAGNOSTIC_CONTRACT_INVALID')
        if doc.get('source_files_manifest_sha256')!=source_manifest_sha:raise ComparisonBlocked('RAW_DIAGNOSTIC_SOURCE_MANIFEST_CHANGED')
        if not isinstance(manifest.get('files'),list):raise ComparisonBlocked('RAW_DIAGNOSTIC_CONTRACT_INVALID')
        if doc.get('approved') is not False or not isinstance(doc.get('channels'),list):raise ComparisonBlocked('RAW_DIAGNOSTIC_CONTRACT_INVALID')
        if any(not isinstance(c,dict) or not isinstance(c.get('grain'),dict) or
               any(not isinstance(c['grain'].get(k),str) for k in ('source_group','station_code','item_code','month')) or
               type(c.get('raw_rows')) is not int or c['raw_rows']<0 or
               not isinstance(c.get('interval_and_grid_diagnostic',{}),dict) for c in doc['channels']):
            raise ComparisonBlocked('RAW_DIAGNOSTIC_CHANNEL_SHAPE_INVALID')
        raw_channels=doc['channels'];input_status='RAW_DIAGNOSTICS_ONLY_UNAPPROVED'
    except (OSError,ValueError) as exc:diagnostic_issues.append(getattr(exc,'code','RAW_DIAGNOSTIC_NOT_AVAILABLE'))
    # A status string is never an approved source count.
    approved=[];source_issues=[]
    from app.services.source_contract_authority import verify_approved_receipt
    for decision in db.query(SourceContractDecision).filter_by(decision='APPROVED').all():
        try:
            verify_approved_receipt(db,decision.receipt,decision.receipt_sha256)
            approved.append(decision.receipt)
        except ValueError as exc:source_issues.append({'contract_id':decision.contract_id,'code':getattr(exc,'code','SOURCE_APPROVAL_INVALID')})
    from app.core.config import settings
    requests_by_scope={};request_issues=[]
    for entry in manifest_catalog()['manifests']:
        if entry['status']=='INVALID':
            request_issues.append({'name':entry['name'],'code':entry['blocker']});continue
        reviewed=inspect_manifest(db,entry['path'],settings.DATASET_SNAPSHOT_DIR,entry['sha256'])
        key=(entry.get('domain'),entry.get('item_id'),entry.get('task'))
        requests_by_scope.setdefault(key,[]).append(reviewed)
    rows=[]
    for coverage in adapter_coverage()['rows']:
        hints=RAW_ITEM_HINTS.get(coverage['item_id'],[]) if coverage['domain']=='fixed_station' else []
        discovered=[c for c in raw_channels if c.get('grain',{}).get('item_code') in hints and c.get('raw_rows',0)>0]
        scopes=[{'grain':c['grain'],'held_rows':c['raw_rows'],'channel_sha256':c.get('channel_sha256'),
                 'grid_status':c.get('interval_and_grid_diagnostic',{}).get('status')} for c in discovered]
        proofs=[p for receipt in approved for p in receipt.get('observations',{}).values()
                if p.get('quantity_kind')==coverage['quantity_kind'] and p.get('standard_variable') in coverage['supported_target_channels']]
        requests=requests_by_scope.get((coverage['domain'],coverage['item_id'],coverage['runtime_task']),[])
        ready=[r for r in requests if r['status']=='READY']
        blockers=[]
        if not proofs:blockers.append('APPROVED_SOURCE_UNIT_CLOCK_QC_PHYSICAL_EPISODE_BINDINGS_MISSING')
        blockers+=['THREE_FIXED_APPROVED_DATASETS_REQUIRED','TASK_SPECIFIC_FEATURES_AND_LABEL_EVIDENCE_REQUIRED',
                   'FIXED_SPLIT_EVALUATION_ACCEPTANCE_AUTHORITIES_REQUIRED','INDEPENDENT_COMPARISON_REVIEW_REQUIRED']
        if ready:blockers=[]
        rows.append({**coverage,'source_status':'READY_FOR_EXACT_MANIFEST' if ready else 'APPROVED_PROOFS_PRESENT_REQUIRES_TASK_PREFLIGHT' if proofs else 'BLOCKED',
                     'raw_inventory_status':'DISCOVERY_HINT_MATCHES_UNAPPROVED' if scopes else 'NO_DISCOVERY_HINT_MATCH',
                     'raw_mapping_authority':'LITERAL_DISCOVERY_ONLY_NOT_STANDARD_VARIABLE_APPROVAL',
                     'discovery_item_hints':hints,'raw_grain_count':len(scopes),'raw_held_rows':sum(s['held_rows'] for s in scopes),
                     'raw_scope_examples':scopes[:8],'approved_source_observations':len(proofs),
                     'training_ready':bool(ready),'reviewed_requests':requests,'operational_ready':None,'blockers':blockers})
    return {'schema_version':'model-task-source-readiness-1','task_keys':72,'scope_status':'REPRESENTATION_BASELINE_SCOPE_PARTIAL',
            'source_inventory_status':input_status,'diagnostic_sha256':diagnostic_sha,'source_manifest_sha256':source_manifest_sha,
            'diagnostic_issues':diagnostic_issues,'source_authority_issues':source_issues,'rows':rows,
            'scope_specific_training_preflight_required':True,'operational_completion':False,
            'request_issues':request_issues,'training_ready_count':sum(r['training_ready'] for r in rows),
            'operational_ready_count':None,'operational_status':'NOT_EVALUATED_IN_SOURCE_INVENTORY',
            'operational_reason':'Current serving/registry authority is reported by the separate MLOps readiness service.',
            'mutation_performed':False}
