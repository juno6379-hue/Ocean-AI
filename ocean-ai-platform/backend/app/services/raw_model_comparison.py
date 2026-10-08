"""Fixed-holdout native-number forecasting experiments, without model authority.

The source's unit, timezone, physical sensor and online availability remain
unresolved. This schema is deliberately incompatible with production workers.
"""
from collections import Counter
import hashlib
import math
from pathlib import Path
import numpy as np
from app.services.qc_raw_diagnostic import canonical, digest, validate_series, RawDiagnosticError

POLICY = 'raw-native-comparison-policy-1'
ARTIFACT = 'raw-native-ridge-artifact-1'
REPORT = 'raw-native-comparison-report-1'
SPLITS = ('TRAIN', 'VALIDATION', 'TEST')


def recipe_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _plan(series, policy):
    times, values = validate_series(series)
    if not isinstance(policy, dict) or policy.get('schema_version') != POLICY:
        raise RawDiagnosticError('RAW_COMPARISON_POLICY_REQUIRED')
    if policy.get('scope') != 'RAW_NATIVE_NUMERIC_DEVELOPMENT_ONLY' or policy.get('holdout_locked') is not True:
        raise RawDiagnosticError('EXPLICIT_RAW_SCOPE_AND_LOCKED_HOLDOUT_REQUIRED')
    membership = policy.get('membership')
    if not isinstance(membership, dict) or set(membership) != set(SPLITS) or any(not isinstance(membership[s], list) for s in SPLITS):
        raise RawDiagnosticError('THREE_FIXED_RAW_SPLITS_REQUIRED')
    flat = sum((membership[s] for s in SPLITS), [])
    if flat != [r['row_id'] for r in series['rows']] or len(set(flat)) != len(flat):
        raise RawDiagnosticError('RAW_SPLIT_MEMBERSHIP_OVERLAP_ORDER_OR_COVERAGE')
    lags, minimum, alphas = policy.get('lag_samples'), policy.get('min_pairs_per_split'), policy.get('ridge_alphas')
    if type(lags) is not int or not 1 <= lags <= 64 or type(minimum) is not int or minimum < 8:
        raise RawDiagnosticError('EXPLICIT_BOUNDED_LAGS_AND_MINIMUM_PAIRS_REQUIRED')
    if not isinstance(alphas, list) or not 1 <= len(alphas) <= 16 or any(type(a) not in {int,float} or not math.isfinite(a) or a <= 0 for a in alphas) or len(set(alphas)) != len(alphas):
        raise RawDiagnosticError('EXPLICIT_POSITIVE_RIDGE_CANDIDATES_REQUIRED')
    if min(map(len,membership.values())) < minimum + lags:
        raise RawDiagnosticError('RAW_SPLIT_TOO_SHORT')
    nt = len(membership['TRAIN'])
    intervals = Counter((times[i]-times[i-1]).total_seconds() for i in range(1,nt))
    modes = [v for v,n in intervals.items() if n == max(intervals.values())]
    if len(modes) != 1 or modes[0] <= 0:
        raise RawDiagnosticError('TRAIN_NATIVE_CADENCE_MODE_AMBIGUOUS')
    cadence = modes[0]
    pairs, exclusions = {}, {}
    begin = 0
    for split in SPLITS:
        end = begin+len(membership[split]); selected = []; excluded = []
        for origin in range(begin,end):
            target = origin+1
            if origin-lags+1 < begin or target >= end:
                excluded.append({'origin_id':series['rows'][origin]['row_id'],'reason':'SPLIT_LOCAL_WARMUP_OR_TARGET_BOUNDARY'});continue
            if any((times[j]-times[j-1]).total_seconds() != cadence for j in range(origin-lags+2,target+1)):
                excluded.append({'origin_id':series['rows'][origin]['row_id'],'reason':'NATIVE_CLOCK_GAP'});continue
            selected.append({'origin_id':series['rows'][origin]['row_id'],'target_id':series['rows'][target]['row_id'],
                'origin_clock_raw':series['rows'][origin]['clock_raw'],'target_clock_raw':series['rows'][target]['clock_raw'],
                'feature_row_ids':[series['rows'][j]['row_id'] for j in range(origin-lags+1,origin+1)],
                'x':values[origin-lags+1:origin+1].tolist(),'target':float(values[target]),'persistence':float(values[origin]),
                'origin_source':series['rows'][origin]['source'],'target_source':series['rows'][target]['source']})
        if len(selected)<minimum:raise RawDiagnosticError('INSUFFICIENT_RAW_COMMON_PAIRS:'+split)
        pairs[split]=selected;exclusions[split]=excluded;begin=end
    return pairs, exclusions, cadence


def _metrics(actual, predicted):
    delta=np.asarray(actual)-np.asarray(predicted)
    return {'mae':float(np.mean(np.abs(delta))),'rmse':float(np.sqrt(np.mean(delta*delta))),'count':len(delta)}


def _predict(model, x):
    x=np.asarray(x,dtype=float)
    return ((x-np.asarray(model['mean']))/np.asarray(model['scale']))@np.asarray(model['coef'])+model['intercept']


def _fit_model(x,y,alpha):
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale==0.,1.,scale)
    z=(x-mean)/scale;intercept=float(y.mean())
    coef=np.linalg.solve(z.T@z+alpha*np.eye(z.shape[1]),z.T@(y-intercept))
    return {'alpha':float(alpha),'mean':mean.tolist(),'scale':scale.tolist(),'coef':coef.tolist(),'intercept':intercept}


def fit_raw_comparison(series,policy):
    pairs,exclusions,cadence=_plan(series,policy)
    train,validation=pairs['TRAIN'],pairs['VALIDATION']
    x=np.asarray([r['x'] for r in train]);y=np.asarray([r['target'] for r in train])
    vx=np.asarray([r['x'] for r in validation]);vy=np.asarray([r['target'] for r in validation])
    candidates=[];models={}
    for alpha in sorted(policy['ridge_alphas']):
        model=_fit_model(x,y,alpha);models[alpha]=model
        candidates.append({'alpha':float(alpha),'validation_metrics':_metrics(vy,_predict(model,vx))})
    chosen=min(candidates,key=lambda c:(c['validation_metrics']['mae'],c['alpha']))
    baseline=_metrics(vy,[r['persistence'] for r in validation])
    recommended='RIDGE' if chosen['validation_metrics']['mae']<baseline['mae'] else 'PERSISTENCE'
    artifact={'schema_version':ARTIFACT,'status':'RAW_DIAGNOSTIC_ONLY','approved':False,'production_eligible':False,
        'source_series_sha256':digest(series),'source_manifest_sha256':series['source_manifest_sha256'],
        'parquet_sha256':series['parquet_sha256'],'grain':series['grain'],'policy':policy,
        'membership_sha256':digest(policy['membership']),'recipe_sha256':recipe_sha256(),
        'source_reader_sha256':__import__('app.services.qc_raw_diagnostic',fromlist=['recipe_sha256']).recipe_sha256(),
        'native_cadence_seconds':cadence,'cadence_authority':'TRAIN_NATIVE_CLOCK_MODE_NOT_APPROVED_SCHEDULE',
        'preprocessing_fit':'TRAIN_ONLY','parameters_fit':'TRAIN_ONLY','selection':'VALIDATION_MAE_ONLY_TEST_NOT_USED',
        'model':models[chosen['alpha']],'validation_candidates':candidates,'validation_persistence_metrics':baseline,
        'development_recommended_candidate':recommended,'pair_counts':{s:len(pairs[s]) for s in SPLITS},
        'pair_membership_sha256':{s:digest([{k:r[k] for k in ('origin_id','target_id','feature_row_ids')} for r in pairs[s]]) for s in SPLITS},
        'unit':None,'timezone':None,'physical_sensor_id':None,'physical_qc':'NOT_EVALUATED',
        'source_qc_interpreted':False,'online_availability':'NOT_ESTABLISHED',
        'excluded_origins':{s:len(exclusions[s]) for s in SPLITS}}
    return {'artifact':artifact,'sha256':digest(artifact)}


def compare_raw_series(series,envelope):
    if not isinstance(envelope,dict) or not isinstance(envelope.get('artifact'),dict) or digest(envelope['artifact'])!=envelope.get('sha256'):
        raise RawDiagnosticError('RAW_COMPARISON_ARTIFACT_CHECKSUM_MISMATCH')
    body=envelope['artifact']
    if fit_raw_comparison(series,body.get('policy'))!=envelope:
        raise RawDiagnosticError('RAW_COMPARISON_ARTIFACT_OR_INPUT_CHANGED')
    pairs,exclusions,_=_plan(series,body['policy']);test=pairs['TEST']
    predictions=_predict(body['model'],[r['x'] for r in test]).tolist()
    paired=[{**row,'ridge':float(predicted)} for row,predicted in zip(test,predictions)]
    report={'schema_version':REPORT,'status':'RAW_DIAGNOSTIC_ONLY','approved':False,'production_eligible':False,
        'source_series_sha256':digest(series),'artifact_sha256':envelope['sha256'],'grain':series['grain'],
        'test_pair_membership_sha256':body['pair_membership_sha256']['TEST'],
        'membership_sha256':body['membership_sha256'],'paired_test_predictions':paired,'exclusions':exclusions,
        'test_metrics':{'RIDGE':_metrics([r['target'] for r in test],predictions),
                        'PERSISTENCE':_metrics([r['target'] for r in test],[r['persistence'] for r in test])},
        'development_recommended_candidate':body['development_recommended_candidate'],
        'operating_model_selected':False,'physical_task_ready':False,'registered_models':0,'deployed_models':0,
        'limitations':['Native clock order does not establish UTC or online availability',
            'Raw numerical error has unresolved physical unit and is not approved forecasting performance',
            'No QC truth, datum, sensor episode, production source/dataset/protocol authority or operational acceptance']}
    report['result_sha256']=digest(report)
    canonical(report)
    return report
