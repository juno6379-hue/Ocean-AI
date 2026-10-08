"""Read-only actual Parquet smoke and exhaustive physical-input review packet.

Usage: python -m app.scripts.review_actual_analysis --config explicit.json
       --output NEW_DIRECTORY
No DB, credentials, source edits or production artifact registration are used.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from app.services.qc_raw_diagnostic import (read_raw_parquet_series, fixed_membership,
    fit_raw_diagnostic, analyze_raw_diagnostic, unevaluated_rule_report, hash_file)
from app.services.anomaly_analysis import source_requirements
from app.services.evidence_fusion import fuse_raw_diagnostics


def run(config, output):
    output = Path(output)
    if output.exists():
        raise ValueError('NEW_OUTPUT_DIRECTORY_REQUIRED')
    when = datetime.now(timezone.utc).isoformat()
    series = read_raw_parquet_series(config['parquet_path'], config['parquet_sha256'],
        config['manifest_path'], config['manifest_sha256'], config['grain'], config['columns'],
        config.get('identifier_transform', 'IDENTITY'), config.get('limit', 500), config.get('offset', 0),
        config.get('ordering', 'RAW_FILE_ORDER'))
    membership = fixed_membership(series, config['train_count'], config['calibration_count'])
    policy = {'schema_version': 'raw-native-diagnostic-policy-1', 'membership': membership,
        'window_samples': config['window_samples'], 'calibration_quantile': config['calibration_quantile'],
        'raw_numeric_scale_floor': config['raw_numeric_scale_floor']}
    artifact = fit_raw_diagnostic(series, policy)
    prediction = analyze_raw_diagnostic(series, artifact)
    rules = unevaluated_rule_report(series, when)
    fusion = fuse_raw_diagnostics(series, artifact, prediction, rules)
    conditional = {'schema_version': 'ocean-anomaly-series-1',
        'scope': {'station_id': None, 'sensor_id': None, 'variable_code': None,
            'unit': None, 'sensor_episode_id': None}, 'as_of': when, 'facts': {},
        'raw_source_grain': series['grain'],
        'rows': [{'row_id': r['row_id'], 'scope': {}, 'timestamp': r['clock_raw'],
            'available_at': None, 'qc_available_at': None, 'qc_eligible': False,
            'value': float(r['value_raw']), 'source': r['source']} for r in series['rows']]}
    requirements = source_requirements(conditional)
    summary = {'schema_version': 'actual-source-analysis-smoke-v1', 'checked_at': when,
        'status': 'RAW_DIAGNOSTIC_EXECUTED_PHYSICAL_CONTRACT_BLOCKED', 'grain': series['grain'],
        'raw_rows': len(series['rows']), 'first_native_clock': series['rows'][0]['clock_raw'],
        'last_native_clock': series['rows'][-1]['clock_raw'], 'splits': {k:len(v) for k,v in membership.items()},
        'source_manifest_sha256': series['source_manifest_sha256'], 'parquet_sha256': series['parquet_sha256'],
        'ordering_audit': series['selection']['ordering_audit'],
        'raw_fit_executed': True, 'physical_fit_executed': False,
        'raw_prediction_summary': prediction['summary'], 'raw_candidates': fusion['raw_numeric_candidate_count'],
        'rule_requested_count': rules['requested_rule_count'], 'rule_result_count': len(rules['results']),
        'physical_rule_summary': rules['summary'], 'physical_fusion_status': fusion['physical_fusion_status'],
        'source_qc_literal_counts': {column: dict(Counter(r['source_qc_raw'][column] for r in series['rows']))
            for column in config['columns'].get('qc', [])},
        'physical_blocker_counts': requirements['requirements']['blocker_counts'],
        'source_units_confirmed': 0, 'source_clocks_confirmed': 0, 'physical_sensors_confirmed': 0,
        'historical_qc_codebook_confirmed': 0, 'approved': False, 'production_eligible': False,
        'registered_models': 0, 'database_writes': 0,
        'limitations': ['Native clock is not UTC; actual receiver/QC availability remains unknown.',
            'Raw numeric scale is not a documented physical unit or calibrated quantity.',
            'Raw literal QC codes including padding remain uninterpreted.',
            'Fixed native-row splits are a development diagnostic, not an approved dataset.',
            'SPIKE/PERSISTENCE candidates have no human truth labels, fault or environment attribution.',
            'Physical Rule12, reference anomaly modes and physical Fusion remain NOT_EVALUATED.']}
    output.mkdir(parents=True)
    files = {'series.json': series, 'policy.json': policy, 'artifact.json': artifact,
        'prediction.json': prediction, 'rule-report.json': rules, 'raw-fusion.json': fusion,
        'physical-input-review-packet.json': conditional, 'physical-readiness.json': requirements,
        'summary.json': summary, 'run-config.json': config}
    for name, data in files.items():
        with (output/name).open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
            stream.write('\n')
    receipt = {'schema_version': 'actual-source-analysis-delivery-v1', 'checked_at': when,
        'files': {name: {'sha256': hash_file(output/name), 'bytes': (output/name).stat().st_size} for name in files},
        'source_files_modified': False, 'database_writes': 0, 'approvals_generated': 0}
    (output/'delivery-manifest.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(json.loads(args.config.read_text(encoding='utf-8')), args.output)
        print(json.dumps({k:result[k] for k in ('status','raw_rows','raw_fit_executed','physical_fit_executed','raw_candidates','physical_rule_summary')}, ensure_ascii=False))
    except Exception as exc:
        # Do not echo source contents, configuration values or connection data.
        print(json.dumps({'status':'FAIL','error_type':type(exc).__name__,'code':str(exc) if isinstance(exc, ValueError) and len(str(exc))<120 else None}))
        raise SystemExit(1)
