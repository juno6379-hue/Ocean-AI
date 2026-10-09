import {useEffect,useRef,useState} from 'react';
import {FlaskConical,Play,CheckCircle2,TriangleAlert} from 'lucide-react';
import {API_BASE_URL,apiFetch} from '../api/client';
import {validSimulationScenarios,validSimulationResult,simulationChartRows} from '../data/operationSimulation';
import {operatingState} from '../data/observationWorkspace';
import ObservationSeriesChart from './ObservationSeriesChart';
import OperationEvidence from './OperationEvidence';

const stageLabel=(value:string)=>value==='EVALUATED'?'평가 완료':value==='ANALYSIS_ONLY'?'분석 완료 · 검토 필요':'미평가';
export default function OperationSimulationPanel({asOfDay,asOfTime}:{asOfDay:string;asOfTime:string}) {
  const [open,setOpen]=useState(false),[scenarios,setScenarios]=useState<any[]>([]),[scenario,setScenario]=useState('');
  const [result,setResult]=useState<any>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const request=useRef<AbortController|null>(null);
  useEffect(()=>{
    setResult(null);setError('');setLoading(false);request.current?.abort();
    return()=>{request.current?.abort();};
  },[asOfDay,asOfTime]);
  useEffect(()=>{
    if(!open||scenarios.length)return;
    const c=new AbortController();
    apiFetch(API_BASE_URL+'/operation-simulation/scenarios',{signal:c.signal}).then(async response=>{if(!response.ok)throw new Error('HTTP '+response.status);return response.json();})
      .then(value=>{if(c.signal.aborted)return;if(!validSimulationScenarios(value))throw new Error('가상 시나리오 출처 확인 실패');setScenarios(value.scenarios);setScenario(value.scenarios[0].scenario_id);})
      .catch(e=>{if(!c.signal.aborted)setError('시나리오 조회 실패: '+e.message);});
    return()=>c.abort();
  },[open,scenarios.length]);
  const selected=scenarios.find(s=>s.scenario_id===scenario);
  const visible=validSimulationResult(result,scenario,asOfDay,asOfTime)?result:null;
  const run=async()=>{
    request.current?.abort();const c=new AbortController();request.current=c;setResult(null);setError('');setLoading(true);
    try{
      const response=await apiFetch(API_BASE_URL+'/operation-simulation/run',{method:'POST',signal:c.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario_id:scenario,as_of_day:asOfDay,as_of_time:asOfTime})});
      if(!response.ok)throw new Error('HTTP '+response.status);
      const value=await response.json();
      if(!validSimulationResult(value,scenario,asOfDay,asOfTime))throw new Error('시나리오·기준시각·시험 전용 결과 확인 실패');
      if(!c.signal.aborted)setResult(value);
    }catch(e){if(!c.signal.aborted)setError('가상 시험 실패: '+(e instanceof Error?e.message:String(e)));}
    finally{if(!c.signal.aborted)setLoading(false);}
  };
  const p=visible?.quality_pipeline,state=visible?operatingState(visible.operation,visible.cutoff_native):null;
  const workflowPassed=Boolean(p&&['pending_stopped','unapproved_resume_blocked','reviewer_required','rejected_resume_blocked','resumed_once'].every(key=>p.workflow[key]===true));
  const chartRows=visible?simulationChartRows(visible):[];
  return <details className="obs-panel obs-simulation" open={open} onToggle={event=>setOpen(event.currentTarget.open)}><summary><FlaskConical size={16}/>운영상태·QC 가상 시험 <span>가상 데이터 · 실제 집계에 포함하지 않음</span></summary>{open&&<div className="obs-simulation-body">
    <p>샘플 자료로 운영 진단 → Rule QC → 이상탐지 AI → Evidence Fusion → 검토 중지·재개를 시험합니다. 실제 관측소 데이터와 승인 상태는 별도로 유지됩니다.</p>
    <div className="obs-simulation-form"><label>시험 시나리오<select aria-label="가상 시험 시나리오" value={scenario} disabled={loading||!scenarios.length} onChange={event=>{request.current?.abort();setScenario(event.target.value);setResult(null);setError('');setLoading(false);}}>{scenarios.map(s=><option key={s.scenario_id} value={s.scenario_id}>{s.label}</option>)}</select></label><button className="obs-primary-button" onClick={run} disabled={loading||!scenario}><Play size={13}/>{loading?'가상 시험 실행 중…':'가상 시험 실행'}</button></div>
    {selected&&<p className="obs-caption">{selected.description} · 기준 {asOfDay} {asOfTime}</p>}
    {error&&<p role="alert" className="obs-error">{error}</p>}
    {!scenarios.length&&!error&&<p role="status" className="obs-caption">시나리오 조회 중…</p>}
    {visible&&<div className="obs-simulation-result"><div className="obs-simulation-result-heading"><strong>가상 시험 결과 · {visible.label}</strong><span className={'obs-status '+(visible.assertions.every((a:any)=>a.passed)?'emerald':'rose')}>{visible.assertions.filter((a:any)=>a.passed).length} / {visible.assertions.length}개 검증 통과</span></div>
      <p className="obs-caption">가상 운영상태 {state?.label} · {visible.cutoff_native} · 실운영 저장 0건</p>
      <div className="obs-simulation-stages"><article><h4>Rule QC</h4><strong>{stageLabel(p.rule.status)}</strong><p>평가 {p.rule.evaluated_count}건 · 이상 {p.rule.anomaly_count}건<br/>미평가 {p.rule.not_evaluated_count}건</p></article><article><h4>이상탐지 AI</h4><strong>{stageLabel(p.ai.status)}</strong><p>평가 {p.ai.evaluated_count}건 · 후보 {p.ai.anomaly_count}건<br/>{Object.entries(p.ai.modes).map(([mode,counts]:[string,any])=>mode+' '+counts.anomaly_count+'/'+counts.evaluated_count+'건').join(' · ')}</p></article><article><h4>Evidence Fusion</h4><strong>{stageLabel(p.fusion.status)}</strong><p>{p.fusion.recommendation} · score {p.fusion.recommendation_score??'—'}<br/>{p.fusion.missing_categories.length?'미확인 근거: '+p.fusion.missing_categories.join(' · '):'연결된 시험 근거 평가'}</p></article><article><h4>Human Approval</h4><strong>{workflowPassed?'중지·재개 검증 통과':'중지·재개 검증 실패'}</strong><p>{p.workflow.transitions.join(' → ')}<br/>검토자·승인 조건은 시험 안에서 확인합니다.</p></article></div>
      <ul className="obs-simulation-assertions">{visible.assertions.map((assertion:any)=><li key={assertion.name}>{assertion.passed?<CheckCircle2 size={14}/>:<TriangleAlert size={14}/>}<span><strong>{assertion.name}</strong><small>{assertion.detail}</small></span><b>{assertion.passed?'통과':'실패'}</b></li>)}</ul>
      <div className="obs-simulation-gates">{[['PENDING에서 후속 실행 중지',p.workflow.pending_stopped],['미승인 재개 차단',p.workflow.unapproved_resume_blocked],['검토자 권한 필요',p.workflow.reviewer_required],['반려 후 재개 차단',p.workflow.rejected_resume_blocked],['승인 후 1회 재개',p.workflow.resumed_once]].map(([label,passed])=><span key={String(label)} className={passed?'passed':'failed'}>{passed?'✓':'!'} {label}</span>)}</div>
      <OperationEvidence operation={visible.operation} expectedEnd={visible.cutoff_native}/>
      <details className="obs-simulation-samples"><summary>가상 관측값·그래프 보기 ({chartRows.length}건 · 기준시각 이후 {visible.rows.length-chartRows.length}건 제외)</summary><ObservationSeriesChart rows={chartRows} item="SIMULATION" label="가상 시험 관측값" sample/><div className="obs-preview-scroll"><table><thead><tr><th>가상 관측시각</th><th>가상값</th><th>가상 QC</th><th>가상 수신시각</th></tr></thead><tbody>{visible.rows.map((row:any,index:number)=><tr key={index}><td>{row.observed_time_raw}</td><td>{row.value_raw==null?'NULL':String(row.value_raw)}</td><td>{row.source_qc_raw==null?'NULL':JSON.stringify(row.source_qc_raw)}</td><td>{row.received_time_raw??'—'}</td></tr>)}</tbody></table></div></details>
      <details className="obs-caption"><summary>시험 결과 식별자</summary><code>{visible.result_sha256}</code></details>
    </div>}
  </div>}</details>;
}
