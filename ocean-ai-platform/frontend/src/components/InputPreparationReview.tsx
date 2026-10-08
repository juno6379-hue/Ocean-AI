import {useRef,useState} from 'react';
import {API_BASE_URL,apiFetch} from '../api/client';

async function read(path:string,init?:RequestInit){
  const response=await apiFetch(`${API_BASE_URL}${path}`,init);const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:data.detail?.detail||data.detail?.code||`HTTP ${response.status}`);
  return data;
}
function download(body:unknown,name:string){
  const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);
}
const hash=(value:unknown)=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
export default function InputPreparationReview({datasets,canWrite,onChanged}:{datasets:any[];canWrite:boolean;onChanged:()=>void}){
  const [legacy,setLegacy]=useState(''),[newId,setNewId]=useState(''),[version,setVersion]=useState(''),[dependencies,setDependencies]=useState('[]');
  const [migration,setMigration]=useState<any>(null),[policyText,setPolicyText]=useState(''),[policy,setPolicy]=useState<any>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const migrationRevision=useRef(0),policyRevision=useRef(0);
  const reset=()=>{migrationRevision.current++;setMigration(null);setError('');setMessage('');};
  const parsedDependencies=()=>{
    const value=JSON.parse(dependencies);
    if(!Array.isArray(value)||value.length>128||value.some(d=>!d||typeof d!=='object'||
      Object.keys(d).sort().join(',')!=='path,role,sha256'||typeof d.path!=='string'||!hash(d.sha256)||
      !['SOURCE_CONTRACT','SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY'].includes(d.role)))
      throw new Error('의존 근거에는 role·허용된 파일 path·64자리 sha256이 필요합니다.');
    return value;
  };
  const migrationReady=migration?.status==='READY_TO_BUILD_NEW_VERSION'&&migration.legacy_dataset_id===legacy&&
    migration.new_dataset_id===newId&&migration.new_dataset_version===version&&hash(migration.legacy_snapshot_sha256)&&hash(migration.review_sha256);
  async function inspectMigration(){
    setBusy(true);reset();const revision=migrationRevision.current;try{
      const params=new URLSearchParams({new_dataset_id:newId,new_version:version,dependencies_json:JSON.stringify(parsedDependencies())});
      const data=await read(`/model-development/datasets/${encodeURIComponent(legacy)}/migration-review?${params}`);
      if(!Array.isArray(data.blockers)||data.approved!==false||data.mutation_performed!==false)throw new Error('전환 검토 응답 형식 미확인');
      if(revision===migrationRevision.current)setMigration(data);
    }catch(reason){setError(reason instanceof Error?reason.message:'전환 검토 실패');}finally{setBusy(false);}
  }
  async function migrate(){
    if(!migrationReady||!canWrite)return;setBusy(true);setError('');try{
      const result=await read(`/model-development/datasets/${encodeURIComponent(legacy)}/migrate-v2`,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({new_dataset_id:newId,new_version:version,dependencies:parsedDependencies(),expected_legacy_sha256:migration.legacy_snapshot_sha256,expected_review_sha256:migration.review_sha256})});
      setMigration(null);setMessage(`새 버전 ${result.dataset_id} · ${result.status}. 기존 원본과 승인은 복사하지 않았습니다. 별도 검증·데이터셋 승인이 필요합니다.`);onChanged();
    }catch(reason){setMigration(null);setError(reason instanceof Error?reason.message:'전환 실패');}finally{setBusy(false);}
  }
  async function inspectPolicy(){
    setBusy(true);setError('');setPolicy(null);const revision=policyRevision.current;try{
      const selection=JSON.parse(policyText);if(!selection||Array.isArray(selection)||typeof selection!=='object')throw new Error('정책 검토 선택 명세가 필요합니다.');
      const result=await read(`/model-development/policy-bundle?${new URLSearchParams({selection_json:JSON.stringify(selection)})}`);
      if(result.approved!==false||!result.protocols)throw new Error('정책 초안 응답 형식 미확인');if(revision===policyRevision.current)setPolicy(result);
    }catch(reason){setError(reason instanceof Error?reason.message:'정책 초안 검토 실패');}finally{setBusy(false);}
  }
  return <details className="border rounded p-3"><summary className="cursor-pointer font-medium">막힌 입력 보완 · 기존 데이터셋 전환·고정 정책 검토</summary>
    <p className="text-xs text-slate-600 mt-2">계정 없이 근거 부족 사유와 정책 초안을 읽을 수 있습니다. 실제 전환은 원천·정책의 최신 승인과 담당 권한을 다시 확인하며, 새 v2를 승인 상태로 만들지 않습니다.</p>
    {error&&<p role="alert" className="text-xs text-red-700 mt-2 break-all">{error}</p>}{message&&<p role="status" className="text-xs text-blue-800 mt-2">{message}</p>}
    <details className="mt-3"><summary className="cursor-pointer">기존 v1 → 새 v2 검토</summary>
      <div className="grid md:grid-cols-3 gap-2 mt-2"><label className="text-xs">기존 데이터셋<select aria-label="전환할 기존 데이터셋" className="block border rounded p-2 w-full" value={legacy} onChange={e=>{setLegacy(e.target.value);reset();}}><option value="">명시적으로 선택</option>{datasets.filter(d=>d.data_hash).map(d=><option value={d.dataset_id} key={d.dataset_id}>{d.dataset_name} · {d.dataset_version} ({d.dataset_id})</option>)}</select></label>
      <label className="text-xs">새 데이터셋 ID<input className="block border rounded p-2 w-full" maxLength={128} value={newId} onChange={e=>{setNewId(e.target.value);reset();}}/></label>
      <label className="text-xs">새 버전<input className="block border rounded p-2 w-full" maxLength={128} value={version} onChange={e=>{setVersion(e.target.value);reset();}}/></label></div>
      <label className="block text-xs mt-2">고정할 원천·분할·평가·수용 정책 근거 (JSON)<textarea aria-label="데이터셋 전환 의존 근거" className="block border rounded p-2 w-full font-mono mt-1" rows={4} maxLength={60000} value={dependencies} onChange={e=>{setDependencies(e.target.value);reset();}}/></label>
      <p className="text-xs text-slate-500">각 근거의 role, 허용 경로 path, 파일 sha256을 명시합니다. 빈 목록으로 검토하면 필요한 승인 근거를 확인할 수 있습니다. 코드명만 바꾸거나 과거 승인을 복사하지 않습니다.</p>
      <div className="flex flex-wrap gap-2 mt-2"><button className="border rounded px-3 py-2 disabled:text-slate-400" disabled={busy||!legacy||!newId||!version} onClick={inspectMigration}>변경 없이 전환 가능 여부 검토</button><button className="bg-blue-600 rounded px-3 py-2 text-white disabled:bg-slate-200 disabled:text-slate-500" disabled={busy||!migrationReady||!canWrite} onClick={migrate}>검증된 근거로 새 BUILT v2 생성</button></div>
      {migration&&<div className="bg-slate-50 rounded p-2 text-xs mt-2"><p>{migrationReady?'재구축 근거 검증됨 · 별도 데이터셋 승인 필요':'전환 차단 · 필요한 근거 보완'}</p>{migration.blockers.map((reason:string,i:number)=><p key={i} className="break-all mt-1">{reason}</p>)}<button className="text-blue-700 mt-2" onClick={()=>download(migration,'dataset-migration-review.json')}>검토 내역 내려받기</button></div>}
    </details>
    <details className="mt-3"><summary className="cursor-pointer">고정 분할·평가·수용 정책 초안 검토</summary>
      <p className="text-xs text-slate-600 mt-2">세 데이터셋 ID, 업무·단일 목표 변수·단위, 분할 전략, embargo, horizon/lookback, Feature ID와 비교 후보를 명시합니다. 성능·시간·비용 수용값은 제안이며 운영 승인이 아닙니다. 수용값 미정은 NOT_DEFINED로 남습니다.</p>
      <label className="text-xs block mt-2">정책 선택 명세 (JSON)<textarea aria-label="고정 정책 선택 명세" className="block border rounded p-2 w-full font-mono mt-1" rows={5} maxLength={60000} value={policyText} onChange={e=>{policyRevision.current++;setPolicyText(e.target.value);setPolicy(null);}}/></label>
      <button className="text-xs text-blue-700 mt-2 mr-3" onClick={()=>{policyRevision.current++;setPolicy(null);setPolicyText(JSON.stringify({domain:'',item_id:'',task:'',target_variable:'',unit:'',
        dataset_ids:{TRAIN:'',VALIDATION:'',TEST:''},protocol_id:'',version:'',feature_ids:[],split_strategy:'',embargo_seconds:null,
        horizon_seconds:null,lookback_seconds:null,ridge_alphas:[],normal_quantiles:[],limits:{},cost_policy:''},null,2));}}>미정값을 남긴 선택 명세 양식</button>
      <button className="border rounded px-3 py-2 mt-2 disabled:text-slate-400" disabled={busy||!policyText} onClick={inspectPolicy}>변경 없이 고정 정책 초안 생성·검토</button>
      {policy&&<div className="bg-slate-50 rounded p-2 text-xs mt-2"><p>초안 · 승인되지 않음 · {policy.acceptance_criteria_status}</p><pre className="whitespace-pre-wrap break-all max-h-72 overflow-auto mt-2">{JSON.stringify(policy,null,2)}</pre><button className="text-blue-700 mt-2" onClick={()=>download(policy,'fixed-model-policy-draft.json')}>정책 초안 내려받기</button></div>}
    </details>
  </details>;
}
