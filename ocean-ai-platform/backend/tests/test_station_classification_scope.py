from types import SimpleNamespace
from app.services.station_classification import resolve_scope,sql_scope,UNKNOWN

class DB:
    def query(self,*args):return self
    def all(self):return [SimpleNamespace(station_id='DT_1',network_type='조위관측소',sea_area='서해'),SimpleNamespace(station_id='TW_1',network_type='해양관측부이',sea_area='남해'),SimpleNamespace(station_id='IE_1',network_type='해양과학기지',sea_area=None)]

def test_classification_is_db_exact_and_unknown_codes_are_distinct():
    assert resolve_scope(DB()) is None
    assert resolve_scope(DB(),'조위관측소','서해')=={'include':['DT_1']}
    assert resolve_scope(DB(),'조위관측소','남해')=={'include':[]}
    assert resolve_scope(DB(),UNKNOWN)=={'exclude':['DT_1','TW_1','IE_1']}
    assert resolve_scope(DB(),UNKNOWN,'서해')=={'include':[]}
    assert sql_scope({'include':[]})==(' AND 0=1',[])
    sql,args=sql_scope({'include':["x' OR 1=1 --"]})
    assert sql==' AND station_code IN (?)' and args==["x' OR 1=1 --"]
