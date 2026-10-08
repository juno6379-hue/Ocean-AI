"""Freeze latest actual-month inputs before fitting safe JSON development models."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from app.services.raw_next_row_training import (VARIABLES,DEFAULT_PERIODS,read_month_source,freeze_membership,
    train_frozen_rows,canonical,digest,immutable,hash_file,RawTrainingError)


def train(source_manifest,expected_sha,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    source=read_month_source(source_manifest,expected_sha)
    manifest={'schema_version':'raw-next-row-source-selection-v1',**{k:v for k,v in source.items() if k not in {'rows','exclusions'}},
              'native_clock_only':True,'unit':None,'timezone':None,'horizon_seconds':None,'nonoperational':True,'experimental':True,
              'ordering':'NATIVE_CLOCK_ASCENDING_AND_EXACT_CELL_TIE_ORDER_NO_ONLINE_AVAILABILITY_ASSUMPTION'}
    source_sha=immutable(output/'source-selection.json',canonical(manifest))
    frozen={}
    # All memberships and policies are written before any model parameters fit.
    for variable in VARIABLES:
        rows=source['rows'][variable]
        membership=freeze_membership(rows,DEFAULT_PERIODS,output/'memberships'/(variable+'.jsonl'))
        immutable(output/'exclusions'/(variable+'.jsonl'),b''.join(canonical(r)+b'\n' for r in source['exclusions'][variable]))
        policy={'schema_version':'raw-next-row-training-policy-v1','task':'NEXT_OBSERVED_ROW_FORECAST','variable_code':variable,
            'source_period':'2026-07','station_code':'DT_0001','source_group':'GR_OBS_ST','source_selection_sha256':source_sha,
            **membership,'native_periods':{s:{'start':a,'end_exclusive':b} for s,(a,b) in DEFAULT_PERIODS.items()},
            'input_lags':3,'ridge_alphas':[.01,.1,1.,10.,100.],'holdout_locked':True,'parameters_fit':'TRAIN_ONLY',
            'selection':'VALIDATION_MAE_ONLY_TIES_PERSISTENCE','target':'NEXT_OBSERVED_NATIVE_ROW_NOT_FIXED_CADENCE',
            'missing_policy':'RETAIN_NATIVE_ROW_AND_EXCLUDE_ANY_NONFINITE_OR_AMBIGUOUS_4_ROW_WINDOW_NO_IMPUTATION',
            'approved':False,'nonoperational':True,'physical_unit':None,'timezone':None,'horizon_seconds':None}
        policy_sha=immutable(output/'policies'/(variable+'.json'),canonical(policy))
        frozen[variable]=(membership,policy,policy_sha)
    if any(a.get('invalid_native_clock_rows',0) for a in source['audit'].values()):
        raise RawTrainingError('INVALID_NATIVE_CLOCK_ORDER_UNRESOLVED_FIT_BLOCKED')
    models=[];recipe=hash_file(Path(__import__('app.services.raw_next_row_training',fromlist=['x']).__file__))
    for variable in VARIABLES:
        membership,policy,policy_sha=frozen[variable];rows=source['rows'][variable]
        fitted=train_frozen_rows(rows,policy)
        last=rows[-3:]
        if any(r['pair_eligible_numeric'] is not True for r in last):raise RawTrainingError('LATEST_3_RAW_VALUES_NOT_ELIGIBLE')
        artifact={'schema_version':'raw-next-row-model-v1','variable_code':variable,'model_id':variable,
            'task':'NEXT_OBSERVED_ROW_FORECAST','source_period':'2026-07','source_group':'GR_OBS_ST','station_code':'DT_0001',
            'input_lags':3,'input_order':'OLDEST_TO_LATEST','selected_model':fitted['selected_model'],'params':fitted['params'],
            'ridge_alpha':fitted['ridge_alpha'] if fitted['selected_model']=='RIDGE' else None,
            'input_semantics':'THREE_FINITE_RAW_NUMBERS_OF_ONE_SOURCE_VARIABLE_NATIVE_ROW_ORDER',
            'output_semantics':'NEXT_OBSERVED_ROW_RAW_NUMBER_WITHOUT_FIXED_TIME_HORIZON',
            **membership,'policy_sha256':policy_sha,'source_selection_sha256':source_sha,'recipe_sha256':recipe,
            'validation_metrics':fitted['validation_metrics'],'test_metrics':fitted['test_metrics'],'pair_counts':fitted['pair_counts'],
            'native_clock_only':True,'experimental':True,'nonoperational':True,'approved':False,'production_eligible':False,
            'unit':None,'timezone':None,'horizon_seconds':None,'source_QC_interpreted':False,
            'parameters_fit':'TRAIN_ONLY','model_selection':'VALIDATION_ONLY_NO_TEST_TUNING','refit_on_validation':False}
        artifact_path='models/'+variable+'.json';artifact_sha=immutable(output/artifact_path,canonical(artifact))
        receipt_common={'schema_version':'raw-next-row-training-receipt-v1','status':'COMPLETED_NON_OPERATIONAL',
            'variable_code':variable,'source_membership_sha256':membership['source_membership_sha256'],
            'source_membership_count':membership['source_membership_count'],'membership_split_counts':membership['membership_split_counts'],
            'artifact_sha256':artifact_sha,'selected_model':fitted['selected_model'],'policy_sha256':policy_sha,
            'source_selection_sha256':source_sha,'recipe_sha256':recipe,'approved':False,'production_eligible':False}
        training_receipt={**receipt_common,'validation_metrics':fitted['validation_metrics'],'alpha_validation_candidates':fitted['alpha_validation_candidates'],
            'ridge_params':fitted['ridge_params'],'ridge_alpha':fitted['ridge_alpha'],'pair_counts':fitted['pair_counts'],
            'pair_membership_sha256':fitted['pair_membership_sha256'],'excluded_origins':fitted['excluded_origins'],
            'parameters_fit':'TRAIN_ONLY','model_selection':fitted['model_selection'],'test_used_for_selection':False,'refit_on_validation':False}
        eval_receipt={**receipt_common,'schema_version':'raw-next-row-evaluation-receipt-v1','test_metrics':fitted['test_metrics'],
            'test_pair_membership_sha256':fitted['pair_membership_sha256']['TEST'],
            'paired_test_predictions':fitted['paired_test_predictions'],'holdout_used_only_for_evaluation':True}
        training_path='receipts/'+variable+'-training.json';eval_path='receipts/'+variable+'-evaluation.json'
        training_sha=immutable(output/training_path,canonical(training_receipt));eval_sha=immutable(output/eval_path,canonical(eval_receipt))
        models.append({'model_id':variable,'variable_code':variable,'selected_model':fitted['selected_model'],
            'artifact_relative_path':artifact_path,'artifact_sha256':artifact_sha,
            'source_membership_relative_path':'memberships/'+variable+'.jsonl',**membership,
            'policy_relative_path':'policies/'+variable+'.json','policy_sha256':policy_sha,
            'training_receipt_relative_path':training_path,'training_receipt_sha256':training_sha,
            'evaluation_receipt_relative_path':eval_path,'evaluation_receipt_sha256':eval_sha,
            'training_receipt_path':training_path,'eval_receipt_relative_path':eval_path,'eval_receipt_sha256':eval_sha,
            'split_counts':membership['membership_split_counts'],'pair_counts':fitted['pair_counts'],
            'validation_metrics':fitted['validation_metrics'],'test_metrics':fitted['test_metrics'],
            'last_values3':[r['numeric_value'] for r in last],'last_native_times3':[r['clock_raw'] for r in last],
            'last_source_locators3':[r['source'] for r in last],'unit':None,'timezone':None,'horizon_seconds':None})
    release={'schema_version':'raw-forecast-release-v1','task':'NEXT_OBSERVED_ROW_FORECAST','source_period':'2026-07',
        'source_group':'GR_OBS_ST','station_code':'DT_0001','experimental':True,'nonoperational':True,'approved':False,
        'production_eligible':False,'native_clock_only':True,'unit':None,'timezone':None,'horizon_seconds':None,
        'models':models,'sources':[source['source']],'source_selection_relative_path':'source-selection.json','source_selection_sha256':source_sha,
        'source_files_manifest':source['source_manifest'],'source_csv_current_preservation_asserted':False,
        'source_QC_columns_present':False,'source_QC_interpreted':False,'recipe_sha256':recipe,
        'limitations':['Raw numbers have no confirmed physical unit or source timezone',
            'Next observed row can cross a native missing-minute interval; no fixed cadence horizon',
            'Source QC and physical episode are not established; no operational registry/approval change']}
    release['release_id']=digest(release)
    release_sha=immutable(output/'release.json',canonical(release))
    receipt={'schema_version':'raw-next-row-fit-run-receipt-v1','status':'COMPLETED_NON_OPERATIONAL','checked_at':datetime.now(timezone.utc).isoformat(),
        'release_id':release['release_id'],'release_sha256':release_sha,'model_count':len(models),'actual_source_rows':sum(m['source_membership_count'] for m in models),
        'approved':False,'production_eligible':False,'live_database_mutations':0,'models':[{k:m[k] for k in ('model_id','selected_model','source_membership_count','split_counts','pair_counts','artifact_sha256','validation_metrics','test_metrics')} for m in models]}
    # Run timestamps are an execution log, not immutable model authority.
    (output/'run-receipt.json').write_bytes(canonical(receipt))
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-manifest',required=True);parser.add_argument('--source-manifest-sha256',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(train(args.source_manifest,args.source_manifest_sha256,args.output),ensure_ascii=False))
