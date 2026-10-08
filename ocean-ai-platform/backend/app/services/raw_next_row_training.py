"""Full native-month numerical development training, with frozen row membership.

No production authority, UTC, physical unit, QC label or cadence is inferred.
The target is the next observed row, which may have an irregular native interval.
"""
from collections import Counter
from datetime import datetime
import hashlib,json,math
from pathlib import Path
import numpy as np

VARIABLES=('AIR_PRES','WATER_TEMP','SALINITY')
COLUMNS=('OBS_POST_ID','OBS_ITEM_CODE','OBS_TIME','OBS_VALUE','META_ID','RECEIVE_TIME','TRACK_SEQ','REMOTE_CHECK')
DEFAULT_PERIODS={'TRAIN':('2026-07-01 00:00:00','2026-07-19 00:00:00'),
                 'VALIDATION':('2026-07-19 00:00:00','2026-07-25 00:00:00'),
                 'TEST':('2026-07-25 00:00:00','2026-08-01 00:00:00')}


class RawTrainingError(ValueError):pass


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def hash_file(path):
    sha=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):sha.update(block)
    return sha.hexdigest()


def immutable(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=raw:raise RawTrainingError('FROZEN_TRAINING_OUTPUT_CHANGED:'+path.name)
    else:
        with path.open('xb') as stream:stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def _guard(path,root):
    path=Path(path);resolved=path.resolve()
    if not resolved.is_relative_to(Path(root).resolve()):raise RawTrainingError('RAW_SOURCE_OUTSIDE_ALLOWED_ROOT')
    for parent in [path.absolute(),*path.absolute().parents]:
        if parent.is_symlink() or getattr(parent,'is_junction',lambda:False)():raise RawTrainingError('SOURCE_REPARSE_REJECTED')
    return resolved


def _number(literal):
    if literal is None or isinstance(literal,str) and not literal.strip():return None,'MISSING'
    try:value=float(literal)
    except (ValueError,TypeError):return None,'NONNUMERIC'
    if isinstance(literal,bool) or not math.isfinite(value):return None,'NONFINITE'
    return value,'FINITE'


def read_month_source(source_manifest,expected_manifest_sha,*,source_root='D:/AI_Observation/data_lake',station='DT_0001',month='2026-07',variables=VARIABLES,max_rows_per_variable=100000):
    """Freshly hash one explicitly selected GR file; preserve every selected cell."""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    manifest_path=Path(source_manifest)
    if hash_file(manifest_path)!=expected_manifest_sha:raise RawTrainingError('SOURCE_MANIFEST_CHANGED')
    manifest=json.loads(manifest_path.read_bytes())
    descriptors=[f for f in manifest.get('files',[]) if f.get('source_group')=='GR_OBS_ST']
    if len(descriptors)!=1 or manifest.get('month')!=month:raise RawTrainingError('EXACT_GR_MONTH_SOURCE_REQUIRED')
    descriptor=descriptors[0];path=_guard(descriptor['path'],source_root)
    before=path.stat()
    if before.st_size!=descriptor['bytes'] or hash_file(path)!=descriptor['sha256']:raise RawTrainingError('PARQUET_HASH_OR_BYTES_CHANGED')
    pf=pq.ParquetFile(path)
    if pf.metadata.num_rows!=descriptor['footer_rows'] or any(c not in pf.schema_arrow.names for c in COLUMNS):raise RawTrainingError('GR_SCHEMA_OR_FOOTER_CHANGED')
    result={v:[] for v in variables};exclusions={v:[] for v in variables}
    audit={v:Counter() for v in variables};last={};format='%Y-%m-%d %H:%M:%S'
    for rg in range(pf.num_row_groups):
        base=0
        for batch in pf.iter_batches(batch_size=65536,row_groups=[rg],columns=list(COLUMNS)):
            mask=pc.and_(pc.equal(batch.column(0),station),pc.is_in(batch.column(1),value_set=__import__('pyarrow').array(list(variables))))
            positions=pc.indices_nonzero(mask).to_pylist()
            selected=batch.filter(mask).to_pylist()
            for pos,literals in zip(positions,selected):
                variable=literals['OBS_ITEM_CODE'];index=base+pos
                audit[variable]['matched_raw_rows']+=1
                cell={'parquet_sha256':descriptor['sha256'],'row_group':rg,'row_index':index,'column':'OBS_VALUE'}
                numeric,status=_number(literals['OBS_VALUE'])
                row={'row_id':digest(cell),'clock_raw':literals['OBS_TIME'],'value_raw':literals['OBS_VALUE'],
                    'numeric_value':numeric,'numeric_status':status,'pair_eligible_numeric':status=='FINITE',
                    'source':{'sha256':descriptor['sha256'],'locator':f'parquet_row_group={rg};row_index={index};column=OBS_VALUE',
                              'row_group':rg,'row_index':index,'column':'OBS_VALUE'},
                    'source_group':'GR_OBS_ST','station_literal':literals['OBS_POST_ID'],'item_literal':variable,
                    'raw_literals':literals,'exclusion_reasons':[]}
                try:stamp=datetime.strptime(row['clock_raw'],format)
                except (ValueError,TypeError):
                    audit[variable]['invalid_native_clock_rows']+=1;row['exclusion_reasons']=['INVALID_NATIVE_CLOCK'];exclusions[variable].append(row);continue
                if stamp.strftime('%Y-%m')!=month:
                    audit[variable]['outside_month_rows']+=1;row['exclusion_reasons']=['OUTSIDE_REQUESTED_NATIVE_MONTH'];exclusions[variable].append(row);continue
                if variable in last and stamp<last[variable]:audit[variable]['original_file_order_reversals']+=1
                last[variable]=stamp;audit[variable][status+'_rows']+=1
                result[variable].append(row)
                if len(result[variable])>max_rows_per_variable:raise RawTrainingError('RAW_TRAINING_ROW_BOUND_EXCEEDED')
            base+=batch.num_rows
    if hash_file(path)!=descriptor['sha256'] or hash_file(manifest_path)!=expected_manifest_sha or path.stat().st_size!=before.st_size:
        raise RawTrainingError('SOURCE_CHANGED_DURING_READ')
    for variable,rows in result.items():
        counts=Counter(r['clock_raw'] for r in rows)
        rows.sort(key=lambda r:(r['clock_raw'],r['source']['row_group'],r['source']['row_index']))
        for row in rows:
            if counts[row['clock_raw']]>1:
                row['pair_eligible_numeric']=False;row['exclusion_reasons'].append('AMBIGUOUS_DUPLICATE_NATIVE_CLOCK')
                audit[variable]['duplicate_native_clock_rows']+=1
        audit[variable]['native_month_rows']=len(rows)
        audit[variable]['physical_QC_evaluated']=0
    return {'source':{'path':str(path),'sha256':descriptor['sha256'],'bytes':before.st_size,'source_group':'GR_OBS_ST',
        'footer_rows':pf.metadata.num_rows},'source_manifest':{'path':str(manifest_path.resolve()),'sha256':expected_manifest_sha},
        'source_period':month,'station_code':station,'identifier_transform':'IDENTITY_NO_TRIM',
        'rows':result,'exclusions':exclusions,'audit':{v:dict(c) for v,c in audit.items()},
        'source_csv_current_preservation_asserted':False,'source_QC_columns_present':False,'approved':False,'production_eligible':False}


def freeze_membership(rows,periods,output_path):
    if not isinstance(rows,list) or not rows:raise RawTrainingError('RAW_MEMBERSHIP_REQUIRED')
    if set(periods)!=set(DEFAULT_PERIODS):raise RawTrainingError('THREE_FIXED_NATIVE_PERIODS_REQUIRED')
    intervals={s:(datetime.strptime(a,'%Y-%m-%d %H:%M:%S'),datetime.strptime(b,'%Y-%m-%d %H:%M:%S')) for s,(a,b) in periods.items()}
    previous=None
    for start,end in intervals.values():
        if start>=end or previous is not None and start<previous:raise RawTrainingError('NATIVE_SPLIT_PERIOD_OVERLAP')
        previous=end
    ids=set();last=None;counts=Counter();ordered={s:[] for s in periods}
    for row in rows:
        if row['row_id'] in ids:raise RawTrainingError('SOURCE_MEMBERSHIP_ROW_REUSE')
        ids.add(row['row_id']);stamp=datetime.strptime(row['clock_raw'],'%Y-%m-%d %H:%M:%S')
        if last is not None and stamp<last:raise RawTrainingError('MEMBERSHIP_NATIVE_ORDER_REQUIRED')
        last=stamp;split=[s for s,(a,b) in intervals.items() if a<=stamp<b]
        if len(split)!=1:raise RawTrainingError('MEMBERSHIP_OUTSIDE_FIXED_PERIODS')
        row['split']=split[0];counts[split[0]]+=1;ordered[split[0]].append(row['row_id'])
    if any(counts[s]<20 for s in periods):raise RawTrainingError('INSUFFICIENT_RAW_FIXED_SPLIT_ROWS')
    raw=b''.join(canonical(row)+b'\n' for row in rows)
    sha=immutable(output_path,raw)
    return {'source_membership_sha256':sha,'source_membership_count':len(rows),'membership_split_counts':dict(counts),
        'split_member_ids_sha256':{s:digest(v) for s,v in ordered.items()}}


def _pairs(rows,lags=3):
    if type(lags) is not int or not 1<=lags<=32:raise RawTrainingError('BOUNDED_LAGS_REQUIRED')
    pairs={s:[] for s in DEFAULT_PERIODS};excluded=Counter()
    for origin,row in enumerate(rows):
        target=origin+1;begin=origin-lags+1
        if begin<0 or target>=len(rows) or any(r['split']!=row['split'] for r in rows[max(0,begin):target+1]):
            excluded[row['split']+':SPLIT_WARMUP_OR_TARGET_BOUNDARY']+=1;continue
        window=rows[begin:target+1]
        if any(r['pair_eligible_numeric'] is not True or r['numeric_status']!='FINITE' or r['numeric_value'] is None for r in window):
            excluded[row['split']+':NONFINITE_MISSING_OR_AMBIGUOUS_NATIVE_WINDOW']+=1;continue
        if any(window[j]['clock_raw']>=window[j+1]['clock_raw'] for j in range(len(window)-1)):
            raise RawTrainingError('PAIR_NATIVE_CLOCK_ORDER_INVALID')
        pairs[row['split']].append({'origin_id':row['row_id'],'target_id':rows[target]['row_id'],
            'feature_row_ids':[r['row_id'] for r in window[:-1]],'origin_clock_raw':row['clock_raw'],
            'target_clock_raw':rows[target]['clock_raw'],'features':[r['numeric_value'] for r in window[:-1]],
            'target':rows[target]['numeric_value'],'persistence':row['numeric_value']})
    if any(len(v)<8 for v in pairs.values()):raise RawTrainingError('INSUFFICIENT_COMMON_NATIVE_PAIRS')
    return pairs,dict(excluded)


def metrics(actual,predicted):
    delta=np.asarray(actual,dtype=float)-np.asarray(predicted,dtype=float)
    if not np.all(np.isfinite(delta)):raise RawTrainingError('NONFINITE_RAW_PREDICTIONS')
    return {'mae':float(np.mean(np.abs(delta))),'rmse':float(np.sqrt(np.mean(delta*delta))),'pair_count':len(delta)}


def predict_params(params,values):
    return ((np.asarray(values,dtype=float)-np.asarray(params['mean']))/np.asarray(params['scale']))@np.asarray(params['coefficients'])+params['intercept']


def train_frozen_rows(rows,policy):
    if policy.get('schema_version')!='raw-next-row-training-policy-v1' or policy.get('task')!='NEXT_OBSERVED_ROW_FORECAST' or policy.get('holdout_locked') is not True:
        raise RawTrainingError('FIXED_NATIVE_TRAINING_POLICY_REQUIRED')
    lags=policy.get('input_lags');alphas=policy.get('ridge_alphas')
    if not isinstance(alphas,list) or not alphas or len(alphas)>16 or any(type(a) not in {float,int} or not math.isfinite(a) or a<=0 for a in alphas):
        raise RawTrainingError('EXPLICIT_POSITIVE_RIDGE_ALPHAS_REQUIRED')
    actual_sha=hashlib.sha256(b''.join(canonical(r)+b'\n' for r in rows)).hexdigest()
    if actual_sha!=policy['source_membership_sha256']:raise RawTrainingError('FROZEN_MEMBERSHIP_BYTES_CHANGED')
    pairs,exclusions=_pairs(rows,lags)
    train,val,test=(pairs[s] for s in DEFAULT_PERIODS)
    x=np.asarray([r['features'] for r in train]);y=np.asarray([r['target'] for r in train])
    vx=np.asarray([r['features'] for r in val]);vy=np.asarray([r['target'] for r in val])
    tx=np.asarray([r['features'] for r in test]);ty=np.asarray([r['target'] for r in test])
    mean=x.mean(0);scale=x.std(0);scale=np.where(scale==0.,1.,scale);z=(x-mean)/scale
    intercept=float(y.mean());params={};alpha_scores=[]
    for alpha in sorted(set(alphas)):
        coefficient=np.linalg.solve(z.T@z+float(alpha)*np.eye(lags),z.T@(y-intercept))
        model={'coefficients':coefficient.tolist(),'intercept':intercept,'mean':mean.tolist(),'scale':scale.tolist()}
        params[alpha]=model;alpha_scores.append({'alpha':float(alpha),'metrics':metrics(vy,predict_params(model,vx))})
    best=min(alpha_scores,key=lambda row:(row['metrics']['mae'],row['alpha']));ridge=params[best['alpha']]
    val_metrics={'RIDGE':best['metrics'],'PERSISTENCE':metrics(vy,[r['persistence'] for r in val])}
    selected='RIDGE' if val_metrics['RIDGE']['mae']<val_metrics['PERSISTENCE']['mae'] else 'PERSISTENCE'
    ridge_predictions=predict_params(ridge,tx).tolist()
    test_metrics={'RIDGE':metrics(ty,ridge_predictions),'PERSISTENCE':metrics(ty,[r['persistence'] for r in test])}
    return {'selected_model':selected,'params':ridge if selected=='RIDGE' else {},'ridge_params':ridge,'ridge_alpha':best['alpha'],
        'validation_metrics':val_metrics,'test_metrics':test_metrics,'alpha_validation_candidates':alpha_scores,
        'pair_counts':{s:len(v) for s,v in pairs.items()},'pair_membership_sha256':{s:digest([{k:r[k] for k in ('origin_id','target_id','feature_row_ids')} for r in v]) for s,v in pairs.items()},
        'paired_test_predictions':[{**row,'ridge':float(prediction),'selected':float(prediction if selected=='RIDGE' else row['persistence'])} for row,prediction in zip(test,ridge_predictions)],
        'excluded_origins':exclusions,'parameters_fit':'TRAIN_ONLY','model_selection':'VALIDATION_MAE_ONLY_TIES_PERSISTENCE',
        'test_used_for_selection':False,'refit_on_validation':False}
