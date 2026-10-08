"""One PostgreSQL classification contract; raw source names are never facility types."""
from collections import Counter
import math
from app.models.domain import StationMetadata

UNKNOWN='__UNREGISTERED__'
UNASSIGNED='__UNASSIGNED__'
LABELS={'HF-Radar':'해수유동관측소 (HF-Radar)'}
def reference_records(rows, as_of_month=None):
    """A July-only document reference, never a mutation of the stored registry."""
    records=[]
    for row in rows:
        if isinstance(row,dict):
            record=dict(row)
        else:
            record={key:getattr(row,key,None) for key in ('station_id','station_name','network_type','sea_area','latitude','longitude')}
        record.update(metadata_network_type=record.get('network_type'),metadata_sea_area=record.get('sea_area'),
                      classification_basis='LEGACY_DB_REFERENCE',reference_month=None,reference_name=None)
        records.append(record)
    if as_of_month is None:
        return records
    from app.services.monthly_report_matching import comparison
    packet=comparison(as_of_month,'GD_OBS_ST_MONTHLY')
    if packet['audit_state']!='CURRENT':
        for record in records:record['classification_basis']='LEGACY_DB_REFERENCE_AUDIT_STALE'
        return records
    bindings={r['station_code']:r for r in packet.get('station_references',[]) if r.get('binding_status')=='COORDINATE_CORROBORATED_UNIQUE'}
    for record in records:
        ref=bindings.get(record['station_id'])
        if not ref:continue
        expected=ref['catalog_identity']
        same=all(record.get(k)==expected.get(k) for k in ('station_name','network_type','sea_area'))
        for key in ('latitude','longitude'):
            actual,wanted=record.get(key),expected.get(key)
            same=same and isinstance(actual,(int,float)) and isinstance(wanted,(int,float)) and math.isclose(actual,wanted,rel_tol=0,abs_tol=1e-10)
        if not same:
            record['classification_basis']='LEGACY_DB_REFERENCE_INPUT_CHANGED'
            continue
        # A matched identity does not establish a coast absent from the publication.
        coast=ref.get('sea_area') or record.get('sea_area')
        record.update(network_type=ref['network_type'],sea_area=coast,reference_name=ref['report_name'],
                      classification_basis='MONTHLY_REPORT_COORDINATE_CORROBORATED',reference_month=as_of_month,
                      reference_document_sha256=packet['publication_sha256'])
    return records


def catalog(db,as_of_month=None):
    rows=reference_records(db.query(StationMetadata).order_by(StationMetadata.station_id).all(),as_of_month)
    networks=Counter(r['network_type'] for r in rows if r['network_type'])
    seas=Counter(r['sea_area'] for r in rows if r['sea_area'])
    return {'basis':'ocean_ai_db.public.station_metadata','total_registered':len(rows),
            'networks':[{'value':key,'label':LABELS.get(key,key),'registered_stations':count} for key,count in sorted(networks.items())],
            'seas':[{'value':key,'label':'해역값 미상 (DB 등록값)' if key=='미상' else key,'registered_stations':count} for key,count in sorted(seas.items())],
            'reference_month':as_of_month,'document_reference_rows':sum(r['reference_month']==as_of_month for r in rows) if as_of_month else 0,
            'note':'등록 분류 참고값입니다. 7월 문서와 명칭·좌표가 유일하게 대응한 코드는 해당 월 문서를 참조합니다. 문서에 해역이 없는 경우 기존 DB 해역을 유지합니다. 등록 수는 운영 중 시설 수 또는 선택 원천의 보유 수가 아닙니다.'}

def resolve_scope(db,network='',sea='',as_of_month=None):
    if not network and not sea:return None
    rows=reference_records(db.query(StationMetadata).all(),as_of_month)
    if network==UNKNOWN:
        return {'exclude':[r['station_id'] for r in rows]} if not sea or sea==UNASSIGNED else {'include':[]}
    # Missing DB classification and a missing DB row are distinct cases.
    matches=[r['station_id'] for r in rows if (not network or r['network_type']==network)
             and (not sea or r['sea_area']==sea or sea==UNASSIGNED and not r['sea_area'])]
    return {'include':matches}

def sql_scope(scope):
    if scope is None:return '',[]
    key='include' if 'include' in scope else 'exclude'
    codes=scope[key]
    if not codes:return (' AND 0=1',[]) if key=='include' else ('',[])
    op='IN' if key=='include' else 'NOT IN'
    return f" AND station_code {op} ({','.join('?' for _ in codes)})",codes
