"""Durable approval boundary. Post-gate stages are pure drafts, never QC/train/deploy."""
from datetime import datetime,timezone
import hashlib,json,uuid
from pathlib import Path
from sqlalchemy import inspect,update,or_
from app.core.database import SessionLocal
from app.core.security import Actor
from app.models.domain import (ObservationStandard,ObservationRaw,QCRuleResult,AILabel,
    OperationLog,SensorMetadata,DocumentIndex,ApprovalHistory)
from app.models.source_observation_binding import SourceObservationBinding
from app.models.source_contracts import SourceContractPacket
from app.models.agent_workflow import AgentWorkflowRun,AgentWorkflowTransition
from app.services.evidence_fusion import (digest,clock,validate_scope,fuse_evidence,rule_evidence,ai_evidence)
from app.services.observation_provenance import raw_for_standard,source_issue

STAGES=['Evidence Collection','Rule/AI/Metadata/Operation/RAG Fusion','Recommendation','Human Approval','Report Draft Agent','MLOps Recommendation']
MODELS={c.__name__:c for c in (ObservationStandard,ObservationRaw,QCRuleResult,AILabel,OperationLog,SensorMetadata,DocumentIndex,SourceObservationBinding,SourceContractPacket,ApprovalHistory)}
class WorkflowError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
def _actor(actor,review=False):
    allowed={'reviewer','admin'} if review else {'operator','reviewer','admin'}
    if not isinstance(actor,Actor) or not actor.user_id or actor.role not in allowed:raise WorkflowError('REVIEWER_REQUIRED' if review else 'OPERATOR_REQUIRED')
def _key(value):
    if not isinstance(value,str) or not 1<=len(value)<=128:raise WorkflowError('IDEMPOTENCY_KEY_REQUIRED')
def _json(value):
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,dict):return {k:_json(v) for k,v in value.items()}
    if isinstance(value,list):return [_json(x) for x in value]
    return value
def _row(row):return {c.key:_json(getattr(row,c.key)) for c in inspect(type(row)).columns}
def _reference(row):return {'model':type(row).__name__,'pk':{c.key:getattr(row,c.key) for c in inspect(type(row)).primary_key},'sha256':digest(_row(row))}
def _rows(db,scope):
    begin=clock(scope['period_start']).replace(tzinfo=None);end=clock(scope['period_end']).replace(tzinfo=None)
    exact={k:scope[k] for k in ('station_id','sensor_id','variable_code')}
    return {'observations':db.query(ObservationStandard).filter_by(**exact,standard_unit=scope['unit']).filter(ObservationStandard.timestamp_utc>=begin,ObservationStandard.timestamp_utc<end).order_by(ObservationStandard.timestamp_utc,ObservationStandard.observation_id).limit(501).all(),
        'rules':db.query(QCRuleResult).filter_by(**exact).filter(QCRuleResult.timestamp_utc>=begin,QCRuleResult.timestamp_utc<end).order_by(QCRuleResult.qc_result_id).limit(501).all(),
        'labels':db.query(AILabel).filter_by(**exact).filter(AILabel.event_start<end,or_(AILabel.event_end.is_(None),AILabel.event_end>=begin)).order_by(AILabel.label_id).limit(501).all(),
        'operations':db.query(OperationLog).filter_by(station_id=scope['station_id'],sensor_id=scope['sensor_id']).filter(OperationLog.event_time>=begin,OperationLog.event_time<end).order_by(OperationLog.id).limit(501).all(),
        'metadata':db.query(SensorMetadata).filter_by(**exact).all()}
def _membership(rows):return {k:[_reference(r)['pk'] for r in values] for k,values in rows.items()}
def _utc_named(stamp):
    # Only the explicitly named UTC observation column has this storage policy.
    return stamp.replace(tzinfo=timezone.utc).isoformat() if stamp and stamp.tzinfo is None else stamp.isoformat() if stamp else None

def collect_evidence(db,scope,query='',rag_search=None):
    scope=validate_scope(scope);rows=_rows(db,scope);refs=[];evidence=[]
    statuses={k:{'status':'MISSING'} for k in ('RULE','AI','METADATA','OPERATION','RAG')}
    refs.extend(_reference(r) for values in rows.values() for r in values)
    observed={r.observation_id:r for r in rows['observations'][:500]};source_inputs=[];file_dependencies=[]
    for o in observed.values():
        raw=raw_for_standard(db,o)
        if raw:refs.append(_reference(raw))
        binding=db.get(SourceObservationBinding,o.observation_id)
        if binding:
            refs.append(_reference(binding));packet=db.get(SourceContractPacket,binding.contract_id);approval=db.get(ApprovalHistory,binding.approval_history_id)
            if packet:
                refs.append(_reference(packet))
                from app.services.source_contract_authority import SOURCE_ROOT
                for descriptor in packet.payload.get('files',[]):
                    if descriptor.get('path'):
                        path=Path(descriptor['path'])
                        file_dependencies.append({'path':str(path if path.is_absolute() else SOURCE_ROOT/path),'sha256':descriptor.get('sha256')})
            if approval:refs.append(_reference(approval))
        proof=binding.payload if binding else {}
        source_inputs.append({'observation_id':o.observation_id,'timestamp_utc':_utc_named(o.timestamp_utc),'value':o.value_standard,'unit':o.standard_unit,
            'source_issue':source_issue(raw),'available_at':proof.get('available_at'),'qc_available_at':proof.get('qc_available_at'),
            'source_sha256':binding.source_sha256 if binding else None,'source_locator':binding.source_row_locator if binding else None})
    for r in rows['rules'][:500]:
        o=observed.get(r.observation_id)
        if not o or source_issue(raw_for_standard(db,o)):continue
        provenance=getattr(r,'provenance_json',None) or {}
        if not isinstance(provenance,dict):provenance={}
        native_scope=provenance.get('evidence_scope',provenance.get('scope',{}))
        rule_scope=dict(native_scope) if isinstance(native_scope,dict) else {}
        facts=provenance.get('source_facts') or {}
        if not isinstance(facts,dict):facts={}
        if facts.get('sensor_episode_id'):rule_scope['sensor_episode_id']=facts['sensor_episode_id']
        available=provenance.get('available_at');event=provenance.get('event_at')
        status=getattr(r,'evaluation_status',None) or 'NOT_EVALUATED'
        if not facts.get('physical_sensor_id') or not facts.get('sensor_episode_id') or not isinstance(facts.get('clock_semantics'),str) or not facts['clock_semantics'] or provenance.get('event_clock_policy')!='EXPLICIT_OFFSET_INSTANT':status='NOT_EVALUATED'
        # Legacy naive executed_at is not an explicit availability policy.
        try:
            if any(rule_scope.get(k)!=scope[k] for k in ('station_id','sensor_id','variable_code','unit')) or clock(event)!=clock(_utc_named(r.timestamp_utc)) or clock(available)!=clock(provenance.get('executed_at_utc')):
                status='NOT_EVALUATED'
        except (ValueError,AttributeError):status='NOT_EVALUATED'
        item=rule_evidence({'observation_id':r.observation_id,'qc_rule_id':r.qc_rule_id,'rule_version':r.rule_version,'result_flag':r.result_flag,
            'evaluation_status':status,'scope':rule_scope,'event_at':event,'available_at':available,'provenance_json':provenance,
            'result_reason':getattr(r,'result_reason',None)})
        item['source_kind']='RULE_RESULT';evidence.append(item)
    for r in rows['labels'][:500]:
        evidence.append({'category':'AI','source_kind':'AI_LABEL','source_id':r.label_id,'source_sha256':digest(_row(r)),'locator':'ai_label:'+r.label_id,
            'scope':{k:getattr(r,k) for k in ('station_id','sensor_id','variable_code')},'event_at':_json(r.event_start),'available_at':None,'assessment':'UNKNOWN',
            'support_strength':0,'result_status':'NOT_EVALUATED','provenance':{'reason':'LABEL_UNIT_AND_AVAILABILITY_UNRESOLVED'},'approved':False})
    for r in rows['metadata']:
        evidence.append({'category':'METADATA','source_kind':'SENSOR_METADATA','source_id':r.sensor_id,'source_sha256':digest(_row(r)),'locator':'sensor_metadata:'+r.sensor_id,
            'scope':{k:getattr(r,k) for k in ('station_id','sensor_id','variable_code')},'event_at':_json(r.install_date),'available_at':None,'assessment':'CONTEXT',
            'support_strength':0,'result_status':'NOT_EVALUATED','provenance':{'reason':'UNIT_PERIOD_AND_AVAILABILITY_UNRESOLVED'},'approved':False})
    for r in rows['operations'][:500]:
        try:detail=json.loads(r.event_detail or '{}')
        except ValueError:detail={}
        if not isinstance(detail,dict):detail={}
        evidence.append({'category':'OPERATION','source_kind':'OPERATION_LOG','source_id':str(r.id),'source_sha256':digest(_row(r)),'locator':'operation_log:'+str(r.id),
            'scope':detail.get('scope',{'station_id':r.station_id,'sensor_id':r.sensor_id}),'event_at':detail.get('event_at'),'available_at':detail.get('available_at'),
            'assessment':'CONTEXT','support_strength':0,'result_status':'EVALUATED' if detail.get('available_at') else 'NOT_EVALUATED','provenance':{'event_type':r.event_type},'approved':False})
    try:
        if rag_search is None:
            from app.rag.hybrid_retriever import hybrid_search
            rag_search=hybrid_search
        result=rag_search(query or '관측 이상 점검 근거',{'station_id':scope['station_id'],'sensor_id':scope['sensor_id'],'variable_code':scope['variable_code'],
            'date_start':scope['period_start'],'date_end':scope['period_end']},10)
        statuses['RAG']={'status':'FOUND' if result.get('results') else 'MISSING','evidence_status':result.get('evidence_status'),'vector_status':result.get('vector_status'),'vector_error':result.get('vector_error')}
        if result.get('vector_status')=='UNAVAILABLE':statuses['RAG']['status']='ERROR' if not result.get('results') else 'PARTIAL'
        for r in result.get('results',[]):
            meta=r.get('metadata') or {};doc=db.query(DocumentIndex).filter_by(chunk_id=r.get('chunk_id')).first()
            if doc:refs.append(_reference(doc))
            evidence.append({'category':'RAG','source_kind':'DOCUMENT_CHUNK','source_id':r.get('chunk_id'),'source_sha256':meta.get('source_sha256'),
                'locator':'page:'+str(r.get('page'))+';chunk:'+str(r.get('chunk_id')),'scope':meta.get('evidence_scope',{}),'event_at':meta.get('event_at'),'available_at':meta.get('available_at'),
                'assessment':'CONTEXT','support_strength':0,'result_status':'EVALUATED','provenance':{'retrieval_method':r.get('retrieval_method'),'similarity':r.get('similarity'),
                    'report_date':r.get('report_date'),'availability_policy':'EXPLICIT_AVAILABLE_AT_REQUIRED_NOT_REPORT_DATE'},'approved':False})
    except Exception as exc:statuses['RAG']={'status':'ERROR','error_type':type(exc).__name__}
    return {'evidence':evidence,'fetch_status':statuses,'references':refs,'db_membership':_membership(rows),'source_inputs':source_inputs,'file_dependencies':file_dependencies,
        'truncated_sections':[k for k,v in rows.items() if len(v)>500],'scope_description':'BOUNDED_DB_ANALYSIS_NOT_CENSUS'}

def _files_current(dependencies):
    if not isinstance(dependencies,list) or len(dependencies)>64:raise WorkflowError('BOUNDED_FILE_DEPENDENCIES_REQUIRED')
    from app.services.source_contract_snapshot import hash_source_file,source_roots
    from app.services.source_contract_authority import SOURCE_ROOT
    for dep in dependencies:
        if not isinstance(dep,dict) or set(dep)!={'path','sha256'}:raise WorkflowError('FILE_DEPENDENCY_SPEC_INVALID')
        try:hash_source_file(dep['path'],source_roots()+[SOURCE_ROOT],dep['sha256'])
        except (ValueError,OSError):raise WorkflowError('INPUT_FILE_CHANGED_OR_UNAVAILABLE')

def analyze_inputs(db,scope,query='',declared_evidence=None,rule_report=None,ai_report=None,rag_search=None,file_dependencies=None):
    scope=validate_scope(scope);bundle=collect_evidence(db,scope,query,rag_search);additions=json.loads(json.dumps(declared_evidence or [],allow_nan=False))
    if rule_report:
        if not isinstance(rule_report,dict):raise WorkflowError('RULE_REPORT_OBJECT_REQUIRED')
        if rule_report.get('result_sha256')!=digest({k:v for k,v in rule_report.items() if k!='result_sha256'}):raise WorkflowError('RULE_REPORT_CHECKSUM_MISMATCH')
        additions.extend(rule_evidence(r) for r in rule_report.get('results',[]))
    if ai_report:
        if not isinstance(ai_report,dict):raise WorkflowError('AI_REPORT_OBJECT_REQUIRED')
        if ai_report.get('results') or ai_report.get('status')=='ANALYSIS_ONLY':
            if ai_report.get('result_sha256')!=digest({k:v for k,v in ai_report.items() if k!='result_sha256'}):raise WorkflowError('AI_REPORT_CHECKSUM_MISMATCH')
        additions.extend(ai_evidence(dict(r,scope=ai_report.get('scope',{}),report_sha256=ai_report.get('result_sha256'),artifact_sha256=ai_report.get('artifact_sha256'))) for r in ai_report.get('results',[]))
    for item in additions:item['authority']='DECLARED_REVIEW_INPUT';item['approved']=False
    bundle['evidence']+=additions;dependencies=list(file_dependencies or [])+bundle['file_dependencies'];dependencies=list({(d['path'],d['sha256']):d for d in dependencies}.values());_files_current(dependencies)
    payload={'scope':scope,'query':query,'bundle':bundle,'file_dependencies':dependencies,'workflow_recipe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'authority':'ANALYSIS_ONLY_NOT_SOURCE_QC_DATASET_OR_MODEL_APPROVAL'}
    return payload,fuse_evidence(scope,bundle['evidence'],bundle['fetch_status'])

def _recommendation_hash(payload,recommendation):return digest({'input_sha256':digest(payload),'recommendation':recommendation})
def _integrity(db,run,current=True):
    if digest(run.payload)!=run.input_sha256 or _recommendation_hash(run.payload,run.recommendation)!=run.recommendation_sha256:raise WorkflowError('WORKFLOW_SNAPSHOT_CHANGED')
    if not current:return
    if run.payload['workflow_recipe_sha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():raise WorkflowError('WORKFLOW_RECIPE_CHANGED')
    if fuse_evidence(run.payload['scope'],run.payload['bundle']['evidence'],run.payload['bundle']['fetch_status'])!=run.recommendation:raise WorkflowError('FUSION_RECIPE_OR_RECOMMENDATION_CHANGED')
    _files_current(run.payload['file_dependencies'])
    for ref in run.payload['bundle']['references']:
        model=MODELS.get(ref.get('model'))
        if model is None:raise WorkflowError('UNKNOWN_SOURCE_REFERENCE')
        row=db.query(model).filter_by(**ref['pk']).populate_existing().first()
        if not row or digest(_row(row))!=ref['sha256']:raise WorkflowError('CURRENT_SOURCE_REFERENCE_CHANGED')
    if _membership(_rows(db,run.payload['scope']))!=run.payload['bundle']['db_membership']:raise WorkflowError('CURRENT_SCOPE_MEMBERSHIP_CHANGED')
def _load(db,workflow_id,lock=True):
    query=db.query(AgentWorkflowRun).filter_by(workflow_id=workflow_id)
    if lock:query=query.with_for_update()
    run=query.populate_existing().first()
    if not run:raise WorkflowError('WORKFLOW_NOT_FOUND')
    return run

def view(run):
    return {'workflow_id':run.workflow_id,'request_key':run.request_key,'status':run.status,'revision':run.revision,'input_sha256':run.input_sha256,
        'recommendation_sha256':run.recommendation_sha256,'scope':run.payload['scope'],'recommendation':run.recommendation,
        'human_approval':{'required':True,'status':run.status,'requested_by':run.requested_by,'approval_history_id':run.approval_history_id},
        'result':run.result,'workflow':STAGES if run.status=='COMPLETED' else STAGES[:4],'analysis_only':True,'definitive_qc':False,'training_started':False,'deployment_performed':False}
def _record(db,run,key,actor,action,old,new,request,approval_id=None):
    record={'workflow_id':run.workflow_id,'revision':run.revision,'actor_id':actor.user_id,'actor_role':actor.role,'action':action,'from_status':old,'to_status':new,
        'request_sha256':digest(request),'recommendation_sha256':run.recommendation_sha256,'approval_history_id':approval_id}
    db.add(AgentWorkflowTransition(workflow_id=run.workflow_id,request_key=key,revision=run.revision,actor_id=actor.user_id,actor_role=actor.role,from_status=old,to_status=new,action=action,
        request_sha256=digest(request),recommendation_sha256=run.recommendation_sha256,approval_history_id=approval_id,record=record,record_sha256=digest(record)));db.flush()
def _transition_valid(transition):
    fields={k:getattr(transition,k) for k in ('workflow_id','revision','actor_id','actor_role','action','from_status','to_status','request_sha256','recommendation_sha256','approval_history_id')}
    return fields==transition.record and digest(fields)==transition.record_sha256

def _replay(db,run,key,actor,request):
    previous=db.query(AgentWorkflowTransition).filter_by(workflow_id=run.workflow_id,request_key=key).first()
    if not previous:return False
    if previous.actor_id!=actor.user_id or previous.request_sha256!=digest(request) or not _transition_valid(previous):raise WorkflowError('IDEMPOTENCY_KEY_REPLAY_MISMATCH')
    return True

def _cas(db,run,expected_status,new_status):
    changed=db.execute(update(AgentWorkflowRun).where(AgentWorkflowRun.workflow_id==run.workflow_id,AgentWorkflowRun.status==expected_status,AgentWorkflowRun.revision==run.revision).values(
        status=new_status,revision=run.revision+1,updated_at=datetime.now(timezone.utc)),execution_options={'synchronize_session':False})
    if changed.rowcount!=1:raise WorkflowError('WORKFLOW_CONCURRENT_CHANGE')
    db.refresh(run)
def start_workflow(db,payload,recommendation,actor,request_key):
    _actor(actor);_key(request_key);existing=db.query(AgentWorkflowRun).filter_by(request_key=request_key).first()
    if existing:
        if existing.requested_by!=actor.user_id or existing.input_sha256!=digest(payload):raise WorkflowError('IDEMPOTENCY_KEY_REPLAY_MISMATCH')
        _integrity(db,existing);return view(existing)
    run=AgentWorkflowRun(workflow_id=str(uuid.uuid4()),request_key=request_key,requested_by=actor.user_id,input_sha256=digest(payload),
        recommendation_sha256=_recommendation_hash(payload,recommendation),payload=payload,recommendation=recommendation,status='PENDING',revision=0,result=None)
    db.add(run);db.flush();_integrity(db,run)
    approval=ApprovalHistory(approval_type='AGENT_WORKFLOW',target_id=run.workflow_id,requested_by=actor.user_id,approval_status='PENDING',comment='recommendation_sha256='+run.recommendation_sha256)
    db.add(approval);db.flush();run.approval_history_id=approval.id
    _record(db,run,request_key,actor,'REQUEST','NEW','PENDING',{'request_key':request_key,'input_sha256':run.input_sha256},approval.id);return view(run)
def _check_expected(run,sha,revision):
    if sha!=run.recommendation_sha256:raise WorkflowError('STALE_RECOMMENDATION_HASH')
    if revision!=run.revision:raise WorkflowError('STALE_WORKFLOW_REVISION')
def decide_workflow(db,workflow_id,actor,request_key,expected_sha,expected_revision,decision,comment=''):
    _actor(actor,True);_key(request_key)
    if decision not in {'APPROVED','REJECTED'}:raise WorkflowError('DECISION_UNSUPPORTED')
    run=_load(db,workflow_id);_integrity(db,run);request={'decision':decision,'expected_sha':expected_sha,'expected_revision':expected_revision,'comment':comment}
    if _replay(db,run,request_key,actor,request):return view(run)
    _check_expected(run,expected_sha,expected_revision)
    if run.status!='PENDING':raise WorkflowError('WORKFLOW_NOT_PENDING')
    approval=ApprovalHistory(approval_type='AGENT_WORKFLOW',target_id=run.workflow_id,requested_by=run.requested_by,approved_by=actor.user_id,approval_status=decision,
        comment='recommendation_sha256='+expected_sha+'\n'+comment)
    db.add(approval);db.flush();_cas(db,run,'PENDING',decision);run.approval_history_id=approval.id
    _record(db,run,request_key,actor,decision,'PENDING',decision,request,approval.id);return view(run)
def cancel_workflow(db,workflow_id,actor,request_key,expected_sha,expected_revision,comment=''):
    _actor(actor);_key(request_key);run=_load(db,workflow_id);_integrity(db,run,current=False)
    if actor.user_id!=run.requested_by and actor.role not in {'reviewer','admin'}:raise WorkflowError('OWNER_OR_REVIEWER_REQUIRED')
    request={'action':'CANCEL','expected_sha':expected_sha,'expected_revision':expected_revision,'comment':comment}
    if _replay(db,run,request_key,actor,request):return view(run)
    _check_expected(run,expected_sha,expected_revision)
    if run.status not in {'PENDING','APPROVED'}:raise WorkflowError('WORKFLOW_NOT_CANCELLABLE')
    old=run.status;approval=ApprovalHistory(approval_type='AGENT_WORKFLOW',target_id=run.workflow_id,requested_by=run.requested_by,approved_by=actor.user_id,approval_status='CANCELLED',comment='recommendation_sha256='+expected_sha+'\n'+comment)
    db.add(approval);db.flush();_cas(db,run,old,'CANCELLED');run.approval_history_id=approval.id
    _record(db,run,request_key,actor,'CANCEL',old,'CANCELLED',request,approval.id);return view(run)
def report_draft_agent(state):
    return {'status':'DRAFT','text':'관측 검토 초안: '+state['recommendation']+'; source/QC/사건 승인은 별도','recommendation_score':state['recommendation_score'],'score_kind':state['score_kind'],'approved':False}
def mlops_agent(state):
    return {'status':'RECOMMENDATION','action':'승인 source/dataset/고정 protocol 준비도 검토','training_enqueued':False,'model_registered':False,'deployment_performed':False}
def resume_workflow(db,workflow_id,actor,request_key,expected_sha,expected_revision,comment=''):
    _actor(actor);_key(request_key);run=_load(db,workflow_id);_integrity(db,run);request={'action':'RESUME','expected_sha':expected_sha,'expected_revision':expected_revision,'comment':comment}
    if _replay(db,run,request_key,actor,request):return view(run)
    _check_expected(run,expected_sha,expected_revision)
    if run.status!='APPROVED':raise WorkflowError('WORKFLOW_APPROVAL_REQUIRED')
    approval=db.query(ApprovalHistory).filter_by(approval_type='AGENT_WORKFLOW',target_id=workflow_id).order_by(ApprovalHistory.id.desc()).first()
    transition=db.query(AgentWorkflowTransition).filter_by(workflow_id=workflow_id,action='APPROVED',approval_history_id=run.approval_history_id).first()
    if (not approval or approval.id!=run.approval_history_id or approval.approval_status!='APPROVED' or approval.requested_by!=run.requested_by or not transition
        or transition.actor_role not in {'reviewer','admin'} or approval.approved_by!=transition.actor_id or not _transition_valid(transition)
        or 'recommendation_sha256='+run.recommendation_sha256+'\n' not in (approval.comment or '')):raise WorkflowError('CURRENT_WORKFLOW_APPROVAL_INVALID')
    _cas(db,run,'APPROVED','RESUMING')
    result={'report_draft':report_draft_agent(run.recommendation),'mlops':mlops_agent(run.recommendation),'workflow_approval_history_id':approval.id,
        'recommendation_sha256':run.recommendation_sha256,'source_qc_dataset_model_approval_granted':False}
    _cas(db,run,'RESUMING','COMPLETED');run.result=result
    _record(db,run,request_key,actor,'RESUME','APPROVED','COMPLETED',request,approval.id);return view(run)
def run_multi_agent_workflow(station_id,sensor_id,variable_code,unit,period_start,period_end,as_of,query=''):
    scope=locals().copy();scope.pop('query')
    with SessionLocal() as db:payload,result=analyze_inputs(db,scope,query)
    return {'status':'PENDING','analysis_only':True,'human_approval':{'required':True,'status':'PENDING','persisted':False},'recommendation':result,
        'workflow':STAGES[:4],'result':None,'report_draft_executed':False,'mlops_executed':False,'note':'demo analysis; authenticated durable workflows are required for decisions/resume'}
