import copy
from datetime import datetime,timedelta
import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from app.services.qc_raw_diagnostic import digest,RawDiagnosticError
from app.services.raw_model_comparison import POLICY,fit_raw_comparison,compare_raw_series


def fixture():
    start=datetime(2023,1,1);grain=dict(source_group='ISOLATED',source_station_code='ST',source_item_code='RAW',depth_step=None,depth_from=None,depth_to=None)
    values=[100+.2*i+np.sin(i/4) for i in range(120)]
    series={'schema_version':'raw-native-diagnostic-series-1','grain':grain,'clock_format':'%Y-%m-%d %H:%M:%S',
        'source_manifest_sha256':'a'*64,'parquet_sha256':'b'*64,'approved':False,'unit':None,'timezone':None,
        'rows':[{'row_id':'r'+str(i),'grain':grain,'clock_raw':(start+timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%S'),
            'value_raw':str(v),'source':{'sha256':'b'*64,'locator':'row='+str(i)}} for i,v in enumerate(values)]}
    policy={'schema_version':POLICY,'scope':'RAW_NATIVE_NUMERIC_DEVELOPMENT_ONLY','holdout_locked':True,
        'membership':{'TRAIN':['r'+str(i) for i in range(60)],'VALIDATION':['r'+str(i) for i in range(60,90)],'TEST':['r'+str(i) for i in range(90,120)]},
        'lag_samples':3,'min_pairs_per_split':8,'ridge_alphas':[.01,.1,1.,10.]}
    return series,policy,values


def test_train_only_scaler_and_ridge_independent_sklearn_oracle():
    series,policy,values=fixture();envelope=fit_raw_comparison(series,policy);report=compare_raw_series(series,envelope)
    artifact=envelope['artifact'];alpha=artifact['model']['alpha']
    x=np.array([values[i-2:i+1] for i in range(2,59)]);y=np.array([values[i+1] for i in range(2,59)])
    scaler=StandardScaler().fit(x);oracle=Ridge(alpha=alpha).fit(scaler.transform(x),y)
    tx=np.array([values[i-2:i+1] for i in range(92,119)])
    expected=oracle.predict(scaler.transform(tx))
    assert np.max(np.abs(expected-np.array([r['ridge'] for r in report['paired_test_predictions']])))<1e-10
    assert artifact['model']['mean']==pytest.approx(scaler.mean_) and artifact['model']['scale']==pytest.approx(scaler.scale_)
    assert report['test_metrics']['RIDGE']['count']==report['test_metrics']['PERSISTENCE']['count']==27
    assert artifact['pair_counts']=={'TRAIN':57,'VALIDATION':27,'TEST':27}
    assert artifact['preprocessing_fit']=='TRAIN_ONLY' and artifact['selection']=='VALIDATION_MAE_ONLY_TEST_NOT_USED'
    assert report['production_eligible'] is False and report['physical_task_ready'] is False
    assert report['operating_model_selected'] is False and report['registered_models']==report['deployed_models']==0


def test_test_values_cannot_change_fitted_parameters_or_alpha():
    series,policy,_=fixture();a=fit_raw_comparison(series,policy)
    altered=copy.deepcopy(series)
    for row in altered['rows'][90:]:row['value_raw']=str(float(row['value_raw'])+9999)
    b=fit_raw_comparison(altered,policy)
    assert a['artifact']['model']==b['artifact']['model']
    assert a['artifact']['validation_candidates']==b['artifact']['validation_candidates']
    assert a['artifact']['development_recommended_candidate']==b['artifact']['development_recommended_candidate']
    assert a['artifact']['source_series_sha256']!=b['artifact']['source_series_sha256']


def test_validation_tunes_candidate_without_refitting_train_scaler():
    series,policy,_=fixture();a=fit_raw_comparison(series,policy)
    altered=copy.deepcopy(series)
    for row in altered['rows'][60:90]:row['value_raw']=str(float(row['value_raw'])+700)
    b=fit_raw_comparison(altered,policy)
    assert a['artifact']['model']['mean']==b['artifact']['model']['mean']
    assert a['artifact']['model']['scale']==b['artifact']['model']['scale']
    assert a['artifact']['validation_candidates']!=b['artifact']['validation_candidates']


@pytest.mark.parametrize('case',['split_overlap','unlocked','nonfinite_alpha','test_first','source_reuse','future_order','altered_artifact'])
def test_raw_comparison_rejects_contract_or_artifact_corruption(case):
    series,policy,_=fixture()
    if case=='split_overlap':policy['membership']['TEST'][0]=policy['membership']['TRAIN'][0]
    if case=='unlocked':policy['holdout_locked']=False
    if case=='nonfinite_alpha':policy['ridge_alphas']=[float('nan')]
    if case=='test_first':policy['membership']['TRAIN'],policy['membership']['TEST']=policy['membership']['TEST'],policy['membership']['TRAIN']
    if case=='source_reuse':series['rows'][10]['source']=series['rows'][0]['source']
    if case=='future_order':series['rows'][10]['clock_raw']=series['rows'][11]['clock_raw']
    if case=='altered_artifact':
        artifact=fit_raw_comparison(series,policy);artifact['artifact']['model']['coef'][0]+=1;artifact['sha256']=digest(artifact['artifact'])
        with pytest.raises(RawDiagnosticError,match='ARTIFACT_OR_INPUT_CHANGED'):compare_raw_series(series,artifact)
    else:
        with pytest.raises(RawDiagnosticError):fit_raw_comparison(series,policy)


def test_native_gap_exclusions_preserve_identical_target_pairs():
    series,policy,_=fixture()
    for row in series['rows'][100:]:
        stamp=datetime.strptime(row['clock_raw'],series['clock_format'])+timedelta(minutes=1)
        row['clock_raw']=stamp.strftime(series['clock_format'])
    artifact=fit_raw_comparison(series,policy);report=compare_raw_series(series,artifact)
    gap=[r for r in report['exclusions']['TEST'] if r['reason']=='NATIVE_CLOCK_GAP']
    assert len(gap)==3
    assert report['test_metrics']['RIDGE']['count']==report['test_metrics']['PERSISTENCE']['count']==24
    assert len(set((r['origin_id'],r['target_id']) for r in report['paired_test_predictions']))==24
