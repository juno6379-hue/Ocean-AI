"""Loopback-only JSON serving for explicitly nonoperational raw-row experiments."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

VARIABLES = frozenset({'AIR_PRES', 'WATER_TEMP', 'SALINITY'})
DEV_FLAGS = {'experimental': True, 'nonoperational': True, 'approved': False, 'production_eligible': False}
MAX_JSON = 16 * 1024 * 1024
MAX_MEMBERSHIP = 96 * 1024 * 1024
RELEASE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
SOURCE_COLUMNS = frozenset({'OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE','META_ID','RECEIVE_TIME','TRACK_SEQ','REMOTE_CHECK'})
NATIVE_PERIODS = {
    'TRAIN':{'start':'2026-07-01 00:00:00','end_exclusive':'2026-07-19 00:00:00'},
    'VALIDATION':{'start':'2026-07-19 00:00:00','end_exclusive':'2026-07-25 00:00:00'},
    'TEST':{'start':'2026-07-25 00:00:00','end_exclusive':'2026-08-01 00:00:00'},
}


class DevelopmentReleaseError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def instant():
    return datetime.now(timezone.utc).isoformat()


def confined(path, root):
    path, root = Path(path).absolute(), Path(root).absolute()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise DevelopmentReleaseError('PATH_OUTSIDE_ALLOWED_ROOT') from error
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise DevelopmentReleaseError('REPARSE_PATH_FORBIDDEN')
        if part.exists():
            stat = part.lstat()
            if part.is_symlink() or getattr(stat, 'st_file_attributes', 0) & 0x400:
                raise DevelopmentReleaseError('REPARSE_PATH_FORBIDDEN')
    # A lexical parent traversal must not be hidden by absolute() behavior.
    if '..' in path.parts:
        raise DevelopmentReleaseError('PARENT_TRAVERSAL_FORBIDDEN')
    return path


def relative(path, root):
    if not isinstance(path, str) or not path or '\\' in path or Path(path).is_absolute() or ':' in path:
        raise DevelopmentReleaseError('RELATIVE_DEPENDENCY_PATH_INVALID')
    return confined(Path(root)/path, root)


def file_sha(path):
    before = path.stat()
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
    after = path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise DevelopmentReleaseError('FILE_CHANGED_DURING_VERIFICATION')
    return sha.hexdigest()


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise DevelopmentReleaseError('DUPLICATE_JSON_KEY')
        obj[key] = value
    return obj


def strict_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(DevelopmentReleaseError('NONFINITE_JSON_NUMBER')))
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, DevelopmentReleaseError):
            raise
        raise DevelopmentReleaseError('JSON_INVALID') from error


def read_json(path, expected_sha=None, maximum=MAX_JSON):
    before = path.stat()
    if before.st_size > maximum:
        raise DevelopmentReleaseError('JSON_FILE_TOO_LARGE')
    with path.open('rb') as stream:
        raw = stream.read(maximum+1)
    after = path.stat()
    if len(raw)>maximum or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise DevelopmentReleaseError('JSON_CHANGED_DURING_READ')
    if expected_sha is not None and (not isinstance(expected_sha,str) or not SHA.fullmatch(expected_sha) or hashlib.sha256(raw).hexdigest()!=expected_sha):
        raise DevelopmentReleaseError('DEPENDENCY_SHA_MISMATCH')
    body = strict_json(raw)
    if not isinstance(body, dict):
        raise DevelopmentReleaseError('JSON_OBJECT_REQUIRED')
    return body, hashlib.sha256(raw).hexdigest()


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (OverflowError,TypeError,ValueError):
        return False


def vector(value, *, positive=False):
    return isinstance(value,list) and len(value)==3 and all(finite(v) and (not positive or v>0) for v in value)


def flags(body):
    if any(body.get(k) is not v for k,v in DEV_FLAGS.items()):
        raise DevelopmentReleaseError('NONOPERATIONAL_FLAGS_REQUIRED')
    if any(body.get(k) is not None for k in ('unit','timezone','horizon_seconds')):
        raise DevelopmentReleaseError('UNCONFIRMED_PHYSICAL_TIME_SEMANTICS')
    if body.get('task')!='NEXT_OBSERVED_ROW_FORECAST' or body.get('native_clock_only') is not True:
        raise DevelopmentReleaseError('RAW_NEXT_ROW_TASK_REQUIRED')


def native_clock(value):
    if not isinstance(value, str):
        raise DevelopmentReleaseError('NATIVE_CLOCK_LITERAL_REQUIRED')
    try:
        clock=datetime.fromisoformat(value.strip())
    except ValueError as error:
        raise DevelopmentReleaseError('NATIVE_CLOCK_INVALID') from error
    if clock.tzinfo is not None or (clock.year,clock.month)!=(2026,7):
        raise DevelopmentReleaseError('NATIVE_JULY_2026_ONLY')
    return clock


def counts(body):
    if not isinstance(body,dict) or set(body)!={'TRAIN','VALIDATION','TEST'} or not all(type(v) is int and v>0 for v in body.values()):
        raise DevelopmentReleaseError('SPLIT_COUNTS_INVALID')
    return body


def validate_artifact(body, variable):
    if body.get('schema_version')!='raw-next-row-model-v1' or body.get('variable_code')!=variable or body.get('input_lags')!=3:
        raise DevelopmentReleaseError('MODEL_ARTIFACT_SCHEMA_INVALID')
    flags(body)
    params=body.get('params')
    if not isinstance(params,dict):
        raise DevelopmentReleaseError('MODEL_PARAMS_INVALID')
    selected=body.get('selected_model')
    if selected=='PERSISTENCE':
        if params:
            raise DevelopmentReleaseError('PERSISTENCE_PARAMS_MUST_BE_EMPTY')
    elif selected=='RIDGE':
        if set(params)!={'coefficients','intercept','mean','scale'} or not vector(params['coefficients']) or not finite(params['intercept']) or not vector(params['mean']) or not vector(params['scale'],positive=True):
            raise DevelopmentReleaseError('RIDGE_PARAMS_INVALID')
    else:
        raise DevelopmentReleaseError('MODEL_KIND_NOT_ALLOWED')
    for key in ('source_membership_sha256',):
        if not isinstance(body.get(key),str) or not SHA.fullmatch(body[key]):
            raise DevelopmentReleaseError('MEMBERSHIP_SHA_REQUIRED')
    return body


def prediction(artifact, values):
    if not vector(values):
        raise DevelopmentReleaseError('EXACTLY_THREE_FINITE_VALUES_REQUIRED')
    if artifact['selected_model']=='PERSISTENCE':
        value=values[-1]
    else:
        p=artifact['params']
        value=sum((x-m)/s*c for x,m,s,c in zip(values,p['mean'],p['scale'],p['coefficients']))+p['intercept']
    if not finite(value):
        raise DevelopmentReleaseError('PREDICTION_NOT_FINITE')
    return value


def verify_membership(path, expected_sha, expected_count, expected_splits, variable, sources, cache):
    import pyarrow.parquet as pq
    if type(expected_count) is not int or not 4<=expected_count<=200000 or path.stat().st_size>MAX_MEMBERSHIP:
        raise DevelopmentReleaseError('MEMBERSHIP_SIZE_INVALID')
    before=path.stat()
    with path.open('rb') as stream:raw=stream.read(MAX_MEMBERSHIP+1)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise DevelopmentReleaseError('MEMBERSHIP_CHANGED_DURING_READ')
    if len(raw)>MAX_MEMBERSHIP or hashlib.sha256(raw).hexdigest()!=expected_sha:
        raise DevelopmentReleaseError('MEMBERSHIP_SHA_MISMATCH')
    rows=raw.splitlines()
    if len(rows)!=expected_count:
        raise DevelopmentReleaseError('MEMBERSHIP_COUNT_MISMATCH')
    ids=set(); split_counts={'TRAIN':0,'VALIDATION':0,'TEST':0}; last=None; latest=[]
    ordered={key:[] for key in split_counts};pair_counts={key:0 for key in split_counts};window=[];previous_split=None
    for line in rows:
        row=strict_json(line)
        if not isinstance(row,dict) or not isinstance(row.get('row_id'),str) or row['row_id'] in ids:
            raise DevelopmentReleaseError('MEMBERSHIP_ID_DUPLICATE_OR_INVALID')
        ids.add(row['row_id'])
        clock=native_clock(row.get('clock_raw'))
        if last is not None and clock<=last:
            raise DevelopmentReleaseError('MEMBERSHIP_CLOCK_NOT_STRICTLY_ORDERED')
        last=clock
        split='TRAIN' if clock.day<19 else 'VALIDATION' if clock.day<25 else 'TEST'
        if row.get('split')!=split:
            raise DevelopmentReleaseError('FIXED_NATIVE_SPLIT_MISMATCH')
        split_counts[split]+=1
        ordered[split].append(row['row_id'])
        source=row.get('source'); literals=row.get('raw_literals')
        if not isinstance(source,dict) or not isinstance(source.get('sha256'),str) or source['sha256'] not in sources or not isinstance(literals,dict) or set(literals)!=SOURCE_COLUMNS or any(v is not None and not isinstance(v,str) for v in literals.values()):
            raise DevelopmentReleaseError('MEMBERSHIP_SOURCE_BINDING_INVALID')
        if row.get('source_group')!='GR_OBS_ST' or row.get('station_literal')!='DT_0001' or row.get('item_literal')!=variable or literals.get('OBS_POST_ID')!=row['station_literal'] or literals.get('OBS_ITEM_CODE')!=variable or literals.get('OBS_TIME')!=row['clock_raw'] or literals.get('OBS_VALUE')!=row.get('value_raw'):
            raise DevelopmentReleaseError('MEMBERSHIP_EXACT_SCOPE_MISMATCH')
        rg,ri=source.get('row_group'),source.get('row_index')
        if type(rg) is not int or type(ri) is not int or rg<0 or ri<0 or source.get('column')!='OBS_VALUE':
            raise DevelopmentReleaseError('SOURCE_LOCATOR_INVALID')
        if source.get('locator') not in {f'parquet_row_group={rg};row_index={ri}',f'parquet_row_group={rg};row_index={ri};column=OBS_VALUE'}:
            raise DevelopmentReleaseError('SOURCE_LOCATOR_LITERAL_MISMATCH')
        sp=sources[source['sha256']]
        key=(str(sp),rg)
        if cache.get('key')!=key:
            table=pq.ParquetFile(sp)
            if rg>=table.metadata.num_row_groups:
                raise DevelopmentReleaseError('SOURCE_ROW_GROUP_OUT_OF_RANGE')
            group=table.read_row_group(rg,columns=sorted(SOURCE_COLUMNS))
            if group.nbytes>128*1024*1024:
                raise DevelopmentReleaseError('SOURCE_ROW_GROUP_MEMORY_LIMIT')
            cache.clear();cache.update(key=key,table=group)
        group=cache['table']
        if ri>=group.num_rows or any(group[k][ri].as_py()!=v for k,v in literals.items()):
            raise DevelopmentReleaseError('SOURCE_RAW_LITERAL_CHANGED')
        number=row.get('numeric_value');literal=row['value_raw']
        if literal is None or not literal.strip():
            actual,status=None,'MISSING'
        else:
            try:
                actual=float(literal);status='FINITE' if finite(actual) else 'NONFINITE'
            except ValueError:actual,status=None,'NONNUMERIC'
        if row.get('numeric_status')!=status or (status=='FINITE' and (not finite(number) or actual!=number)) or (status!='FINITE' and number is not None) or row.get('pair_eligible_numeric') is not (status=='FINITE'):
            raise DevelopmentReleaseError('RAW_NUMERIC_VALUE_MISMATCH')
        eligible=status=='FINITE'
        if split!=previous_split:window=[];previous_split=split
        window.append(eligible);window=window[-4:]
        if len(window)==4 and all(window):pair_counts[split]+=1
        if eligible:
            latest.append((number,row['clock_raw'],row['row_id'],source));latest=latest[-3:]
    if split_counts!=expected_splits:
        raise DevelopmentReleaseError('MEMBERSHIP_SPLIT_COUNTS_MISMATCH')
    return {'latest':latest,'pair_counts':pair_counts,'split_member_ids_sha256':{key:digest(value) for key,value in ordered.items()}}


def validate_release(directory, allowed_source_roots):
    directory=confined(directory,directory)
    manifest,manifest_sha=read_json(relative('release-manifest.json',directory))
    if manifest.get('schema_version')!='raw-forecast-release-v1' or not isinstance(manifest.get('release_id'),str) or not RELEASE_ID.fullmatch(manifest['release_id']) or manifest.get('source_period')!='2026-07':
        raise DevelopmentReleaseError('RELEASE_MANIFEST_INVALID')
    flags(manifest)
    source_specs=manifest.get('sources')
    if not isinstance(source_specs,list) or not 1<=len(source_specs)<=8:
        raise DevelopmentReleaseError('SOURCE_DESCRIPTORS_REQUIRED')
    sources={}
    for source in source_specs:
        if not isinstance(source,dict) or not isinstance(source.get('path'),str) or not isinstance(source.get('sha256'),str) or not SHA.fullmatch(source['sha256']) or type(source.get('bytes')) is not int:
            raise DevelopmentReleaseError('SOURCE_DESCRIPTOR_INVALID')
        path=None
        for root in allowed_source_roots:
            try:
                path=confined(source['path'],root);break
            except DevelopmentReleaseError:
                pass
        if path is None or path.suffix!='.parquet' or not path.is_file() or path.stat().st_size!=source['bytes'] or file_sha(path)!=source['sha256']:
            raise DevelopmentReleaseError('SOURCE_FILE_UNVERIFIED')
        if source['sha256'] in sources:
            raise DevelopmentReleaseError('SOURCE_DESCRIPTOR_DUPLICATE')
        sources[source['sha256']]=path
    specs=manifest.get('models')
    if not isinstance(specs,list) or len(specs)!=3 or any(not isinstance(s,dict) or not isinstance(s.get('variable_code'),str) for s in specs) or {s['variable_code'] for s in specs}!=VARIABLES:
        raise DevelopmentReleaseError('EXACT_THREE_MODELS_REQUIRED')
    if manifest.get('source_group')!='GR_OBS_ST' or manifest.get('source_table')!='GR_OBS_ST' or manifest.get('station_code')!='DT_0001':
        raise DevelopmentReleaseError('RELEASE_EXACT_SOURCE_SCOPE_REQUIRED')
    selection_path=manifest.get('source_selection_relative_path')
    if selection_path!='source-selection.json':raise DevelopmentReleaseError('SOURCE_SELECTION_PATH_INVALID')
    selection,_=read_json(relative(selection_path,directory),manifest.get('source_selection_sha256'))
    if selection.get('schema_version')!='raw-next-row-source-selection-v1' or selection.get('source_period')!='2026-07' or selection.get('station_code')!='DT_0001' or selection.get('identifier_transform')!='IDENTITY_NO_TRIM' or any(selection.get(k) is not v for k,v in DEV_FLAGS.items()) or selection.get('native_clock_only') is not True or any(selection.get(k) is not None for k in ('unit','timezone','horizon_seconds')):
        raise DevelopmentReleaseError('SOURCE_SELECTION_CONTRACT_INVALID')
    selected_source=selection.get('source')
    if not isinstance(selected_source,dict) or selected_source.get('sha256') not in sources or selected_source.get('source_group')!='GR_OBS_ST' or str(sources[selected_source['sha256']])!=str(Path(selected_source.get('path',''))) or sources[selected_source['sha256']].stat().st_size!=selected_source.get('bytes'):
        raise DevelopmentReleaseError('SOURCE_SELECTION_DESCRIPTOR_MISMATCH')
    if not isinstance(manifest.get('recipe_sha256'),str) or not SHA.fullmatch(manifest['recipe_sha256']):
        raise DevelopmentReleaseError('RECIPE_SHA_REQUIRED')
    loaded={};dependencies={'release-manifest.json':manifest_sha,selection_path:manifest['source_selection_sha256']};cache={}
    for spec in specs:
        variable=spec['variable_code']
        if spec.get('artifact_relative_path')!=f'models/{variable}.json':
            raise DevelopmentReleaseError('ARTIFACT_PATH_NOT_ALLOWLISTED')
        artifact,_=read_json(relative(spec['artifact_relative_path'],directory),spec.get('artifact_sha256'))
        validate_artifact(artifact,variable)
        if spec.get('source_membership_sha256')!=artifact['source_membership_sha256']:
            raise DevelopmentReleaseError('ARTIFACT_MEMBERSHIP_MISMATCH')
        expected_splits=counts(spec.get('membership_split_counts'))
        if counts(spec.get('split_counts'))!=expected_splits:
            raise DevelopmentReleaseError('UI_SPLIT_COUNTS_MISMATCH')
        if artifact.get('source_membership_count')!=spec.get('source_membership_count') or artifact.get('membership_split_counts')!=expected_splits:
            raise DevelopmentReleaseError('ARTIFACT_MEMBERSHIP_COUNT_MISMATCH')
        if artifact.get('source_group')!='GR_OBS_ST' or artifact.get('station_code')!='DT_0001' or artifact.get('source_period')!='2026-07' or artifact.get('parameters_fit')!='TRAIN_ONLY' or artifact.get('refit_on_validation') is not False or artifact.get('model_selection')!='VALIDATION_ONLY_NO_TEST_TUNING' or artifact.get('recipe_sha256')!=manifest['recipe_sha256'] or artifact.get('source_selection_sha256')!=manifest['source_selection_sha256']:
            raise DevelopmentReleaseError('ARTIFACT_FIXED_TRAINING_CONTRACT_INVALID')
        policy_path=spec.get('policy_relative_path')
        if policy_path!=f'policies/{variable}.json':raise DevelopmentReleaseError('POLICY_PATH_NOT_ALLOWLISTED')
        policy,_=read_json(relative(policy_path,directory),spec.get('policy_sha256'))
        if artifact.get('policy_sha256')!=spec['policy_sha256'] or policy.get('schema_version')!='raw-next-row-training-policy-v1' or policy.get('variable_code')!=variable or policy.get('native_periods')!=NATIVE_PERIODS or policy.get('input_lags')!=3 or policy.get('holdout_locked') is not True or policy.get('parameters_fit')!='TRAIN_ONLY' or policy.get('selection')!='VALIDATION_MAE_ONLY_TIES_PERSISTENCE' or policy.get('target')!='NEXT_OBSERVED_NATIVE_ROW_NOT_FIXED_CADENCE' or policy.get('ridge_alphas')!=[0.01,0.1,1.0,10.0,100.0] or policy.get('missing_policy')!='RETAIN_NATIVE_ROW_AND_EXCLUDE_ANY_NONFINITE_OR_AMBIGUOUS_4_ROW_WINDOW_NO_IMPUTATION':
            raise DevelopmentReleaseError('FIXED_NATIVE_POLICY_INVALID')
        if policy.get('source_group')!='GR_OBS_ST' or policy.get('station_code')!='DT_0001' or policy.get('source_period')!='2026-07' or policy.get('source_membership_sha256')!=spec['source_membership_sha256'] or policy.get('source_membership_count')!=spec['source_membership_count'] or policy.get('membership_split_counts')!=expected_splits or policy.get('source_selection_sha256')!=manifest['source_selection_sha256'] or policy.get('approved') is not False or policy.get('nonoperational') is not True or any(policy.get(k) is not None for k in ('physical_unit','timezone','horizon_seconds')):
            raise DevelopmentReleaseError('POLICY_SOURCE_BINDING_INVALID')
        dependencies[policy_path]=spec['policy_sha256']
        membership=spec.get('source_membership_relative_path')
        if membership!=f'memberships/{variable}.jsonl':
            raise DevelopmentReleaseError('MEMBERSHIP_PATH_NOT_ALLOWLISTED')
        membership_review=verify_membership(relative(membership,directory),spec['source_membership_sha256'],spec.get('source_membership_count'),expected_splits,variable,sources,cache)
        latest=membership_review['latest']
        if any(container.get('split_member_ids_sha256')!=membership_review['split_member_ids_sha256'] for container in (spec,artifact,policy)) or spec.get('pair_counts')!=membership_review['pair_counts'] or artifact.get('pair_counts')!=spec['pair_counts']:
            raise DevelopmentReleaseError('EXACT_SPLIT_OR_PAIR_MEMBERSHIP_MISMATCH')
        if spec.get('last_values')!=[v[0] for v in latest] or spec.get('last_native_times')!=[v[1] for v in latest]:
            raise DevelopmentReleaseError('LAST_NATIVE_INPUTS_MISMATCH')
        if spec.get('last_source_locators3')!=[v[3] for v in latest]:raise DevelopmentReleaseError('LAST_SOURCE_LOCATORS_MISMATCH')
        for alias,main in [('last_values3','last_values'),('last_native_times3','last_native_times')]:
            if alias in spec and spec[alias]!=spec[main]:raise DevelopmentReleaseError('LAST_NATIVE_ALIASES_CONFLICT')
        for kind in ('training','eval'):
            key=kind+'_receipt_relative_path';hash_key=kind+'_receipt_sha256'
            path=spec.get(key)
            if path not in {f'receipts/{variable}-{kind}.json',f'{kind}-receipt.json',f'receipts/{kind}-receipt.json'}:
                raise DevelopmentReleaseError('RECEIPT_PATH_NOT_ALLOWLISTED')
            receipt,_=read_json(relative(path,directory),spec.get(hash_key))
            binding=receipt.get('models',{}).get(variable) if isinstance(receipt.get('models'),dict) else receipt
            if not isinstance(binding,dict) or binding.get('source_membership_sha256')!=spec['source_membership_sha256'] or binding.get('artifact_sha256')!=spec['artifact_sha256'] or binding.get('selected_model')!=artifact['selected_model']:
                raise DevelopmentReleaseError('RECEIPT_MODEL_BINDING_MISMATCH')
            if any(binding.get(key)!=spec.get(key) for key in ('validation_metrics','test_metrics','split_counts','membership_split_counts','source_membership_count')) or binding.get('policy_sha256')!=spec['policy_sha256'] or binding.get('source_selection_sha256')!=manifest['source_selection_sha256'] or binding.get('recipe_sha256')!=manifest['recipe_sha256'] or binding.get('approved') is not False or binding.get('production_eligible') is not False:
                raise DevelopmentReleaseError('RECEIPT_EVALUATION_METRICS_MISMATCH')
            if kind=='training' and (binding.get('parameters_fit')!='TRAIN_ONLY' or binding.get('refit_on_validation') is not False or binding.get('test_used_for_selection') is not False or binding.get('model_selection')!='VALIDATION_MAE_ONLY_TIES_PERSISTENCE' or binding.get('pair_counts')!=spec['pair_counts']):
                raise DevelopmentReleaseError('RECEIPT_TRAIN_ONLY_SELECTION_REQUIRED')
            if kind=='eval' and binding.get('holdout_used_only_for_evaluation') is not True:
                raise DevelopmentReleaseError('HOLDOUT_EVALUATION_CONTRACT_REQUIRED')
            dependencies[path]=spec[hash_key]
        for kind in ('validation_metrics','test_metrics'):
            metrics=spec.get(kind)
            if not isinstance(metrics,dict) or set(metrics)!={'PERSISTENCE','RIDGE'} or artifact.get(kind)!=metrics:
                raise DevelopmentReleaseError('EVALUATION_METRICS_REQUIRED')
            for metric in metrics.values():
                if not isinstance(metric,dict) or not finite(metric.get('mae')) or not finite(metric.get('rmse')) or metric['mae']<0 or metric['rmse']<0 or type(metric.get('pair_count')) is not int or metric['pair_count']<=0:
                    raise DevelopmentReleaseError('EVALUATION_METRICS_INVALID')
                if metric['pair_count']!=spec['pair_counts']['VALIDATION' if kind=='validation_metrics' else 'TEST']:
                    raise DevelopmentReleaseError('METRIC_PAIR_COUNT_MISMATCH')
        selected='PERSISTENCE' if spec['validation_metrics']['PERSISTENCE']['mae']<=spec['validation_metrics']['RIDGE']['mae'] else 'RIDGE'
        if artifact['selected_model']!=selected or spec.get('selected_model')!=selected:
            raise DevelopmentReleaseError('VALIDATION_SELECTION_MISMATCH')
        dependencies[spec['artifact_relative_path']]=spec['artifact_sha256'];dependencies[membership]=spec['source_membership_sha256']
        loaded[variable]={'artifact':artifact,'spec':spec}
    for sha,path in sources.items():
        if file_sha(path)!=sha:
            raise DevelopmentReleaseError('SOURCE_CHANGED_DURING_MEMBERSHIP_VERIFICATION')
    pinned=manifest.get('pinned_dependencies')
    if manifest.get('dependency_contract_version')!=2 or not isinstance(pinned,list) or len(pinned)!=len(dependencies)-1 or any(not isinstance(entry,dict) or set(entry)!={'path','sha256'} or not isinstance(entry.get('path'),str) or not isinstance(entry.get('sha256'),str) for entry in pinned):
        raise DevelopmentReleaseError('COMPLETE_PINNED_DEPENDENCIES_REQUIRED')
    if len({entry['path'] for entry in pinned})!=len(pinned) or {entry['path']:entry['sha256'] for entry in pinned}!={key:sha for key,sha in dependencies.items() if key!='release-manifest.json'}:
        raise DevelopmentReleaseError('PINNED_DEPENDENCY_SET_MISMATCH')
    return {'manifest':manifest,'manifest_sha256':manifest_sha,'models':loaded,'dependencies':dependencies,'sources':sources}


class ReleaseStore:
    def __init__(self, deployment_root, *, allowed_source_roots):
        self.root=confined(deployment_root,deployment_root)
        self.allowed_source_roots=list(allowed_source_roots)
        self._lock=threading.RLock();self._current=None;self._pointer_sha=None;self._blocker='NO_VALIDATED_RELEASE'

    def register(self, candidate_directory):
        with self._lock:
            candidate=validate_release(candidate_directory,self.allowed_source_roots)
            release_id=candidate['manifest']['release_id']
            directory=relative('releases/'+release_id,self.root)
            if directory.exists():
                existing=validate_release(directory,self.allowed_source_roots)
                if existing['manifest_sha256']!=candidate['manifest_sha256']:
                    raise DevelopmentReleaseError('IMMUTABLE_RELEASE_ID_REUSED')
            else:
                parent=relative('releases',self.root);parent.mkdir(parents=True,exist_ok=True)
                temporary=relative('.pending-'+release_id,self.root)
                if temporary.exists():
                    raise DevelopmentReleaseError('INCOMPLETE_RELEASE_REVIEW_REQUIRED')
                temporary.mkdir()
                for path,sha in candidate['dependencies'].items():
                    source=relative(path,candidate_directory);target=relative(path,temporary)
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
                    if file_sha(target)!=sha:
                        raise DevelopmentReleaseError('COPIED_RELEASE_SHA_MISMATCH')
                copied=validate_release(temporary,self.allowed_source_roots)
                if copied['manifest_sha256']!=candidate['manifest_sha256']:
                    raise DevelopmentReleaseError('COPIED_RELEASE_CHANGED')
                temporary.replace(directory)
            pointer={'release_id':release_id,'manifest_sha256':candidate['manifest_sha256'],'registered_at':instant(),**DEV_FLAGS}
            self.root.mkdir(parents=True,exist_ok=True)
            temporary=relative('active-release.tmp',self.root);temporary.write_bytes(canonical(pointer));temporary.replace(relative('active-release.json',self.root))
            self._pointer_sha=None
            return pointer

    def current(self):
        with self._lock:
            try:
                pointer,pointer_sha=read_json(relative('active-release.json',self.root),maximum=16384)
                if not isinstance(pointer.get('release_id'),str) or not RELEASE_ID.fullmatch(pointer['release_id']):
                    raise DevelopmentReleaseError('ACTIVE_RELEASE_POINTER_INVALID')
                if any(pointer.get(k) is not v for k,v in DEV_FLAGS.items()):
                    raise DevelopmentReleaseError('ACTIVE_POINTER_FLAGS_INVALID')
                if pointer_sha!=self._pointer_sha:
                    release=validate_release(relative('releases/'+pointer['release_id'],self.root),self.allowed_source_roots)
                    if release['manifest_sha256']!=pointer.get('manifest_sha256'):
                        raise DevelopmentReleaseError('ACTIVE_RELEASE_HASH_MISMATCH')
                    self._current,self._pointer_sha=release,pointer_sha
                # Verify exact frozen dependency and source bytes on every request.
                # Only the row-level Parquet join is cached after activation.
                for name,sha in self._current['dependencies'].items():
                    if file_sha(relative('releases/'+pointer['release_id']+'/'+name,self.root))!=sha:
                        raise DevelopmentReleaseError('ACTIVE_RELEASE_DEPENDENCY_CHANGED')
                for sha,path in self._current['sources'].items():
                    if file_sha(confined(path,next(r for r in self.allowed_source_roots if Path(path).is_relative_to(Path(r)))))!=sha:
                        raise DevelopmentReleaseError('ACTIVE_SOURCE_FILE_CHANGED')
                self._blocker=None
                return self._current
            except (DevelopmentReleaseError,OSError,ValueError,KeyError,TypeError) as error:
                self._blocker=error.code if isinstance(error,DevelopmentReleaseError) else 'ACTIVE_RELEASE_UNAVAILABLE'
                return None

    def readiness(self):
        release=self.current()
        return {'status':'READY' if release else 'BLOCKED','release_id':release['manifest']['release_id'] if release else None,
                'model_count':len(release['models']) if release else 0,'blockers':[] if release else [self._blocker],**DEV_FLAGS}

    def details(self):
        release=self.current()
        if release is None:
            return self.readiness()
        return {'status':'READY','release_id':release['manifest']['release_id'],'source_period':'2026-07','manifest_sha256':release['manifest_sha256'],
                'source_table':'GR_OBS_ST','station_code':'DT_0001',
                'models':[{'model_id':variable,**{k:v for k,v in entry['spec'].items() if k in {'variable_code','artifact_sha256','source_membership_sha256','split_counts','membership_split_counts','source_membership_count','pair_counts','validation_metrics','test_metrics','last_values','last_native_times','last_source_locators3'}},
                          'selected_model':entry['artifact']['selected_model'],'input_lags':3} for variable,entry in release['models'].items()],
                'task':'NEXT_OBSERVED_ROW_FORECAST','native_clock_only':True,'unit':None,'timezone':None,'horizon_seconds':None,**DEV_FLAGS}


def create_app(store):
    app=FastAPI(title='Experimental raw next-row forecast',version='1',docs_url=None,redoc_url=None)

    @app.middleware('http')
    async def loopback(request,call_next):
        try:
            allowed=request.url.hostname in {'127.0.0.1','localhost','::1'} and request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
        except ValueError:
            allowed=False
        if not allowed:
            return JSONResponse(status_code=403,content={'detail':{'code':'LOOPBACK_ONLY'}})
        origin=request.headers.get('origin')
        if origin is not None and origin not in {'http://127.0.0.1:5174','http://localhost:5174'}:
            return JSONResponse(status_code=403,content={'detail':{'code':'LOCAL_DEVELOPMENT_UI_ORIGIN_REQUIRED'}})
        if request.method=='POST' and request.headers.get('content-type','').split(';',1)[0].strip().lower()!='application/json':
            return JSONResponse(status_code=415,content={'detail':{'code':'JSON_CONTENT_TYPE_REQUIRED'}})
        return await call_next(request)

    @app.get('/health')
    def health():
        return {'status':'OK','server_kind':'LOOPBACK_EXPERIMENTAL_RAW_FORECAST',**DEV_FLAGS}

    @app.get('/readiness')
    def readiness():
        return store.readiness()

    @app.get('/release')
    def release():
        return store.details()

    @app.post('/predict')
    async def predict(request:Request):
        raw=bytearray()
        async for block in request.stream():
            raw.extend(block)
            if len(raw)>16384:
                raise HTTPException(413,detail={'code':'PREDICTION_BODY_TOO_LARGE'})
        try:
            body=strict_json(bytes(raw))
            if not isinstance(body,dict) or set(body)!={'model_id','values','expected_release_id','expected_artifact_sha256'} or not isinstance(body.get('model_id'),str) or body['model_id'] not in VARIABLES or not vector(body.get('values')):
                raise DevelopmentReleaseError('PREDICTION_INPUT_INVALID')
            current=store.current()
            if not current:
                raise HTTPException(503,detail={'code':'NO_VALIDATED_DEVELOPMENT_RELEASE'})
            model=current['models'][body['model_id']]
            if body['expected_release_id']!=current['manifest']['release_id'] or body['expected_artifact_sha256']!=model['spec']['artifact_sha256']:
                raise HTTPException(409,detail={'code':'SELECTED_RELEASE_OR_ARTIFACT_CHANGED'})
            value=prediction(model['artifact'],body['values'])
        except DevelopmentReleaseError as error:
            raise HTTPException(422,detail={'code':error.code}) from error
        return {'model_id':body['model_id'],'prediction':value,'input_values':body['values'],'release_id':current['manifest']['release_id'],
                'artifact_sha256':model['spec']['artifact_sha256'],'source_membership_sha256':model['spec']['source_membership_sha256'],
                'task':'NEXT_OBSERVED_ROW_FORECAST','prediction_target':'NEXT_OBSERVED_NATIVE_ROW','native_clock_only':True,
                'unit':None,'timezone':None,'horizon_seconds':None,**DEV_FLAGS}

    return app
