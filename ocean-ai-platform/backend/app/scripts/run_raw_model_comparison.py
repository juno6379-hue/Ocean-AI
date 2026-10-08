"""Read-only actual-source experiment; writes only its explicitly named output."""
import argparse,json
from pathlib import Path
from app.services.qc_raw_diagnostic import read_raw_parquet_series,fixed_membership,digest,canonical,fit_raw_diagnostic,analyze_raw_diagnostic
from app.services.raw_model_comparison import fit_raw_comparison,compare_raw_series,POLICY


def run(config_path,output):
    config_path=Path(config_path);config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    series=read_raw_parquet_series(config['parquet_path'],config['parquet_sha256'],config['manifest_path'],config['manifest_sha256'],
        config['grain'],config['columns'],config['identifier_transform'],config['limit'],config.get('offset',0),config.get('ordering','RAW_FILE_ORDER'))
    peer_series=json.loads((config_path.parent/'series.json').read_text(encoding='utf-8'))
    if digest(series)!=digest(peer_series):raise ValueError('PEER_SOURCE_SERIES_REPLAY_MISMATCH')
    membership=fixed_membership(series,config['train_count'],config['calibration_count'])
    policy={'schema_version':POLICY,'scope':'RAW_NATIVE_NUMERIC_DEVELOPMENT_ONLY','holdout_locked':True,
        'membership':{'TRAIN':membership['TRAIN'],'VALIDATION':membership['CALIBRATION'],'TEST':membership['TEST']},
        'membership_origin':'EXACT_PEER_TRAIN_CALIBRATION_TEST_IDS_CALIBRATION_RENAMED_VALIDATION_FOR_FORECASTING',
        'lag_samples':3,'min_pairs_per_split':8,'ridge_alphas':[0.01,0.1,1.,10.],
        'policy_authority':'UNAPPROVED_ENGINEERING_EXPERIMENT_NO_OPERATIONAL_ACCEPTANCE'}
    artifact=fit_raw_comparison(series,policy);report=compare_raw_series(series,artifact)
    peer_policy=json.loads((config_path.parent/'policy.json').read_text(encoding='utf-8'))
    peer_artifact=fit_raw_diagnostic(series,peer_policy);peer_prediction=analyze_raw_diagnostic(series,peer_artifact)
    old_artifact=json.loads((config_path.parent/'artifact.json').read_text(encoding='utf-8'))
    old_prediction=json.loads((config_path.parent/'prediction.json').read_text(encoding='utf-8'))
    if peer_artifact!=old_artifact or peer_prediction!=old_prediction:raise ValueError('PEER_NATIVE_DIAGNOSTIC_REPLAY_MISMATCH')
    review={'schema_version':'peer-raw-diagnostic-review-1','status':'EXACT_REPLAY_MATCH','approved':False,
        'series_sha256':digest(series),'artifact_sha256':peer_artifact['sha256'],'prediction_sha256':peer_prediction['result_sha256'],
        'ordering_audit':series['selection']['ordering_audit'],'source_record_count':len(series['rows']),
        'authority':'READ_ONLY_SOURCE_REHASH_AND_FITTED_PREDICTION_REPLAY_NOT_PHYSICAL_APPROVAL'}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,body in [('series.json',series),('policy.json',policy),('artifact.json',artifact),('comparison.json',report),('peer-review.json',review)]:
        target=output/name;raw=canonical(body)
        if target.exists() and target.read_bytes()!=raw:raise ValueError('EXPERIMENT_OUTPUT_ALREADY_EXISTS_WITH_DIFFERENT_BYTES')
        target.write_bytes(raw)
    return {'status':report['status'],'test_metrics':report['test_metrics'],'artifact_sha256':artifact['sha256'],
        'report_sha256':report['result_sha256'],'peer_review':review['status'],'production_eligible':False,'output':str(output)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(run(args.config,args.output),ensure_ascii=False))
