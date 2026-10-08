"""One PostgreSQL classification contract; raw source names are never facility types."""
from collections import Counter
from app.models.domain import StationMetadata

UNKNOWN='__UNREGISTERED__'
UNASSIGNED='__UNASSIGNED__'
LABELS={'HF-Radar':'해수유동관측소 (HF-Radar)'}
def catalog(db):
    rows=db.query(StationMetadata).order_by(StationMetadata.station_id).all()
    networks=Counter(r.network_type for r in rows if r.network_type)
    seas=Counter(r.sea_area for r in rows if r.sea_area)
    return {'basis':'ocean_ai_db.public.station_metadata','total_registered':len(rows),
            'networks':[{'value':key,'label':LABELS.get(key,key),'registered_stations':count} for key,count in sorted(networks.items())],
            'seas':[{'value':key,'label':'해역값 미상 (DB 등록값)' if key=='미상' else key,'registered_stations':count} for key,count in sorted(seas.items())],
            'note':'현재 DB 분류 참고값입니다. 등록 관측소 수는 운영 중 관측소 수 또는 선택 원천의 보유 수가 아닙니다.'}

def resolve_scope(db,network='',sea=''):
    if not network and not sea:return None
    rows=db.query(StationMetadata.station_id,StationMetadata.network_type,StationMetadata.sea_area).all()
    if network==UNKNOWN:
        return {'exclude':[r.station_id for r in rows]} if not sea or sea==UNASSIGNED else {'include':[]}
    # Missing DB classification and a missing DB row are distinct cases.
    matches=[r.station_id for r in rows if (not network or r.network_type==network)
             and (not sea or r.sea_area==sea or sea==UNASSIGNED and not r.sea_area)]
    return {'include':matches}

def sql_scope(scope):
    if scope is None:return '',[]
    key='include' if 'include' in scope else 'exclude'
    codes=scope[key]
    if not codes:return (' AND 0=1',[]) if key=='include' else ('',[])
    op='IN' if key=='include' else 'NOT IN'
    return f" AND station_code {op} ({','.join('?' for _ in codes)})",codes
