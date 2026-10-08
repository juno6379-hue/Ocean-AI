# 파일 역할: 관측 사건 관련 요청을 검증하고 API 응답을 제공합니다.
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.domain import EventRegistry
from app.core.security import current_actor, require_reviewer, Actor
from app.models.domain import DocumentIndex, OperationLog
from app.models.evidence import SensorAlias, MDCSensorCatalog
from app.services import event_evidence as evidence

router = APIRouter(prefix="/api/events", tags=["Events"])


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    station_id: Optional[str] = None
    sensor_id: Optional[str] = None
    variable_code: Optional[str] = None
    event_start: datetime
    event_end: Optional[datetime] = None
    severity: Optional[str] = "INFO"
    source_type: str = Field(default="API", min_length=1, max_length=50)
    status: str = Field(default="OPEN", max_length=30)


@router.get("")
def list_events(
    station_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(EventRegistry)
    if station_id:
        query = query.filter(EventRegistry.station_id == station_id)
    if event_type:
        query = query.filter(EventRegistry.event_type == event_type)
    if status:
        query = query.filter(EventRegistry.status == status)
    return {"events": query.order_by(EventRegistry.event_start.desc()).limit(limit).all(), "is_demo": False}


@router.post("", status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    payload.event_start = evidence.utc(payload.event_start, require_offset=True)
    payload.event_end = evidence.utc(payload.event_end, require_offset=True)
    if payload.event_end is not None and payload.event_end <= payload.event_start:
        raise HTTPException(422, 'Event end must be after start')
    if payload.sensor_id:
        evidence.validate_scope(db,payload.station_id,payload.sensor_id,payload.variable_code)
    event = EventRegistry(event_id=f"EVT-{uuid.uuid4().hex}", **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{event_id}/status")
def update_event_status(event_id: str, status: str = Query(..., min_length=1, max_length=30), db: Session = Depends(get_db)):
    event = db.query(EventRegistry).filter(EventRegistry.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.status = status
    if status in {"RESOLVED", "CLOSED"} and event.event_end is None:
        raise HTTPException(409, 'Provide the actual event end; review time is not event time')
    db.commit()
    db.refresh(event)
    return event


def event_operator(actor: Actor = Depends(current_actor)):
    if actor.role not in {'operator','reviewer','admin'}:
        raise HTTPException(403,'Operator role required')
    return actor


class AliasCreate(BaseModel):
    station_id: str
    sensor_id: str
    variable_code: str
    alias_text: str = Field(min_length=1,max_length=200)
    mapping_version: str = Field(min_length=1,max_length=100)
    valid_start: datetime
    valid_end: Optional[datetime] = None


@router.post('/sensor-aliases')
def add_sensor_alias(req: AliasCreate, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    evidence.validate_scope(db,req.station_id,req.sensor_id,req.variable_code)
    start,end=evidence.utc(req.valid_start,True),evidence.utc(req.valid_end,True)
    if end and end<=start: raise HTTPException(422,'Invalid alias validity period')
    alias_id=evidence.digest([req.station_id,req.sensor_id,evidence.normalize_alias(req.alias_text),req.mapping_version])
    old=db.get(SensorAlias,alias_id)
    if old:
        if old.valid_start!=start or old.valid_end!=end: raise HTTPException(409,'Create a new mapping version')
        return old
    row=SensorAlias(alias_id=alias_id,**req.model_dump(exclude={'valid_start','valid_end'}),
                    valid_start=start,valid_end=end,reviewed_by=actor.user_id)
    db.add(row);db.commit();db.refresh(row)
    return row


class SensorResolve(BaseModel):
    station_id: str
    variable_code: str
    expression: str = Field(min_length=1,max_length=200)
    event_start: datetime
    event_end: Optional[datetime] = None


@router.post('/resolve-sensor')
def resolve_sensor(req: SensorResolve,db: Session=Depends(get_db)):
    start,end=evidence.utc(req.event_start,True),evidence.utc(req.event_end,True)
    if end is not None and end<=start: raise HTTPException(422,'Invalid event interval')
    return evidence.resolve_sensor(db,req.station_id,req.variable_code,req.expression,start,end)


@router.get('/reference-catalog')
def reference_catalog(station_id: Optional[str]=None,db: Session=Depends(get_db)):
    from app.models.domain import StationMetadata, SensorMetadata, MDCItemMapping
    stations=db.query(StationMetadata);sensors=db.query(SensorMetadata);aliases=db.query(SensorAlias)
    if station_id:
        stations=stations.filter_by(station_id=station_id);sensors=sensors.filter_by(station_id=station_id)
        aliases=aliases.filter_by(station_id=station_id)
    return {'stations':stations.order_by(StationMetadata.station_id).limit(500).all(),
        'sensors':sensors.order_by(SensorMetadata.sensor_id).limit(500).all(),
        'reviewed_aliases':aliases.filter_by(active=True).order_by(SensorAlias.alias_id).limit(500).all(),
        'variable_mappings':db.query(MDCItemMapping).filter_by(active=True).order_by(MDCItemMapping.source_item_code).all(),
        'counts':{'stations':stations.count(),'sensors':sensors.count(),'aliases':aliases.count()},'is_demo':False}


@router.get('/mdc-sensor-catalog')
def mdc_sensor_catalog(station_id: Optional[str]=None, catalog_version: Optional[str]=None,
                       offset: int=Query(0, ge=0), limit: int=Query(100, ge=1, le=500),
                       db: Session=Depends(get_db)):
    # 원본과 검토 필요 사유를 함께 제공하며 소스 목록을 승인된 장비 별칭으로 취급하지 않는다.
    query = db.query(MDCSensorCatalog)
    if station_id: query = query.filter_by(station_id=station_id)
    if catalog_version: query = query.filter_by(catalog_version=catalog_version)
    return {'items': query.order_by(MDCSensorCatalog.catalog_version, MDCSensorCatalog.sensor_id).offset(offset).limit(limit).all(),
            'total': query.count(), 'is_demo': False, 'identity_scope': 'SOURCE_CHANNEL_REQUIRES_REVIEW'}


class DocumentEventCreate(SensorResolve):
    chunk_id: str
    event_type: str = Field(min_length=1,max_length=100)
    period_quote: str = Field(min_length=1,max_length=4000)
    operation_quote: Optional[str] = None
    operation_time: Optional[datetime] = None


@router.post('/from-document')
def event_from_document(req: DocumentEventCreate,db: Session=Depends(get_db),actor: Actor=Depends(event_operator)):
    start,end=evidence.utc(req.event_start,True),evidence.utc(req.event_end,True)
    if end is not None and end<=start: raise HTTPException(422,'Invalid event interval')
    document=db.query(DocumentIndex).filter_by(chunk_id=req.chunk_id).first()
    if not document: raise HTTPException(404,'Document chunk not found')
    if req.period_quote not in (document.chunk_text or ''):
        raise HTTPException(422,'Period quote must occur in source chunk')
    match=evidence.resolve_sensor(db,req.station_id,req.variable_code,req.expression,start,end)
    if match['status']!='RESOLVED': raise HTTPException(409,match)
    sensor=match['candidates'][0]
    event_id='EVT-'+evidence.digest([req.chunk_id,req.station_id,sensor['sensor_id'],req.variable_code,start,end,req.event_type])[:40]
    event=db.get(EventRegistry,event_id)
    if event: return {'event_id':event_id,'status':event.status,'created':False,'sensor_match':sensor}
    event=EventRegistry(event_id=event_id,event_type=req.event_type,station_id=req.station_id,
        sensor_id=sensor['sensor_id'],variable_code=req.variable_code,event_start=start,event_end=end,
        source_type='DOCUMENT_PERIOD_REVIEW',status='CANDIDATE')
    db.add(event);db.flush()
    evidence.link_evidence(db,event,'DOCUMENT',req.chunk_id,actor.user_id,
        {'quote':req.period_quote,'period_source':'OPERATOR_CONFIRMED_QUOTE','sensor_match':sensor,
         'event_start_utc':start.isoformat(),'event_end_utc':end.isoformat() if end else None,
         'report_date':document.document_date.isoformat() if document.document_date else None})
    if req.operation_quote is not None:
        operation_time=evidence.utc(req.operation_time,True)
        if not req.operation_quote or req.operation_quote not in document.chunk_text or not evidence.in_period(operation_time,start,end):
            raise HTTPException(422,'Operation quote and actual operation time are required')
        # 보고서의 운영 기록을 전사하며 조치를 실제 실행한 것으로 표시하지 않는다.
        operation=OperationLog(station_id=req.station_id,sensor_id=sensor['sensor_id'],event_time=operation_time,
            event_type=req.event_type,event_detail=req.operation_quote,operator='DOCUMENT_RECORD',related_document_id=document.document_id)
        db.add(operation);db.flush()
        evidence.link_evidence(db,event,'OPERATION_LOG',operation.id,actor.user_id,
                               {'source':'DOCUMENT_RECORD','chunk_id':req.chunk_id,'quote':req.operation_quote})
    db.commit()
    return {'event_id':event_id,'status':event.status,'created':True,'sensor_match':sensor}


class EvidenceCreate(BaseModel):
    kind: str
    target_id: str
    quote: Optional[str] = None


@router.post('/{event_id}/evidence')
def add_event_evidence(event_id: str,req: EvidenceCreate,db: Session=Depends(get_db),actor: Actor=Depends(event_operator)):
    event=evidence.get_event(db,event_id,lock=True)
    row=evidence.link_evidence(db,event,req.kind,req.target_id,actor.user_id,{'quote':req.quote} if req.quote else None)
    db.commit()
    return {'link_id':row.link_id,'event_id':event_id}


@router.post('/{event_id}/link-observations')
def link_event_observations(event_id: str,db: Session=Depends(get_db),actor: Actor=Depends(event_operator)):
    count=evidence.attach_observations(db,evidence.get_event(db,event_id,True),actor.user_id)
    db.commit()
    return {'event_id':event_id,'observations':count,'rule':'UTC_HALF_OPEN_V1'}


@router.get('/{event_id}/lineage')
def get_event_lineage(event_id: str,db: Session=Depends(get_db)):
    return evidence.event_lineage(db,event_id)


@router.get('/evidence/{kind}/{target_id}')
def get_reverse_lineage(kind: str,target_id: str,db: Session=Depends(get_db)):
    return evidence.reverse_lineage(db,kind,target_id)


class CandidateCreate(BaseModel):
    label_version: str = Field(min_length=1,max_length=100)


@router.post('/{event_id}/label-candidates')
def propose_label(event_id: str,req: CandidateCreate,db: Session=Depends(get_db),actor: Actor=Depends(event_operator)):
    label=evidence.create_label_candidate(db,evidence.get_event(db,event_id,True),actor.user_id,req.label_version)
    db.commit();db.refresh(label)
    return {'label_id':label.label_id,'review_status':label.review_status,'quality_label':label.quality_label,
            'is_recommendation':True,'event_id':event_id}


@router.post('/{event_id}/features')
def event_features(event_id: str,db: Session=Depends(get_db),actor: Actor=Depends(event_operator)):
    from app.services.evidence_features import generate_event_features
    result=generate_event_features(db,evidence.get_event(db,event_id,True))
    db.commit()
    return result


@router.get('/feature-lineage/{observation_id}/{feature_id}/{feature_version}')
def feature_lineage(observation_id: str,feature_id: str,feature_version: str,db: Session=Depends(get_db)):
    from app.models.domain import ObservationStandard, FeatureValue, DatasetRegistry
    from app.models.evidence import FeatureProvenance, DatasetMembership
    observation=db.get(ObservationStandard,observation_id)
    provenance=db.get(FeatureProvenance,(observation_id,feature_id,feature_version))
    if not observation or not provenance: raise HTTPException(404,'Feature provenance not found')
    value=db.get(FeatureValue,(observation.station_id,observation.sensor_id,observation.variable_code,
        observation.timestamp_utc,feature_id,feature_version))
    if not value: raise HTTPException(404,'Feature value not found')
    datasets=db.query(DatasetRegistry.dataset_id).join(DatasetMembership,
        DatasetMembership.dataset_id==DatasetRegistry.dataset_id).filter(
        DatasetMembership.observation_id==observation_id,DatasetRegistry.feature_version==feature_version).all()
    return {'feature_id':feature_id,'feature_version':feature_version,'value':value.feature_value,
            'provenance':{c.name:getattr(provenance,c.name) for c in provenance.__table__.columns},
            'datasets':[r[0] for r in datasets],'observation_lineage':evidence.reverse_lineage(db,'OBSERVATION',observation_id)}


class EventClose(BaseModel):
    event_end: datetime
    source_quote: str = Field(min_length=1,max_length=4000)


@router.post('/{event_id}/close')
def close_event(event_id: str,req: EventClose,db: Session=Depends(get_db),actor: Actor=Depends(event_operator)):
    from app.models.domain import AuditLog
    from app.models.evidence import EventEvidence
    event=evidence.get_event(db,event_id,True)
    if event.event_end is not None or db.query(EventEvidence).filter(EventEvidence.event_id==event_id,EventEvidence.label_id.is_not(None)).first():
        raise HTTPException(409,'Closed or labelled event is immutable; create a new reviewed event')
    end=evidence.utc(req.event_end,True)
    if end<=event.event_start: raise HTTPException(422,'Event end must be after start')
    graph=evidence.event_lineage(db,event_id)
    documents=[r for r in graph['evidence'] if r['kind']=='DOCUMENT' and req.source_quote in r['chunk']]
    if not documents: raise HTTPException(422,'Closing time requires a quote from linked document evidence')
    for item in graph['evidence']:
        if item['kind'] in {'OBSERVATION','QC_RESULT','OPERATION_LOG'}:
            timestamp=item['data'].get('timestamp_utc',item['data'].get('event_time'))
            if not evidence.in_period(timestamp,event.event_start,end):
                raise HTTPException(409,'Closing interval excludes linked evidence')
    event.event_end=end;event.status='CLOSED'
    for document in documents:
        link=db.get(EventEvidence,document['link_id'])
        link.provenance={**link.provenance,'closing_quote':req.source_quote,'event_end_utc':end.isoformat(),
                         'closing_reviewed_by':actor.user_id}
    db.add(AuditLog(actor=actor.user_id,action='EVENT_INTERVAL_CLOSED',resource_type='EventRegistry',resource_id=event_id,
                   detail_json={'event_end_utc':end.isoformat(),'source_quote':req.source_quote}))
    db.commit()
    return {'event_id':event_id,'status':'CLOSED','event_end':end}
