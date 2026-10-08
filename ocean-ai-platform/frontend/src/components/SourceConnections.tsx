// Administrator tests are read-only; success never starts live ingestion.
import { useState } from 'react';
import { API_BASE_URL, apiClient } from '../api/client';

export default function SourceConnections() {
  const [sources,setSources]=useState<any[]>([]);
  const [results,setResults]=useState<Record<string,any>>({});
  const [error,setError]=useState('');
  const [busy,setBusy]=useState('');
  const load=async()=>{
    setError('');
    try{const r=await apiClient.get(`${API_BASE_URL}/integrations`);setSources(r.data.sources);}
    catch{setError('관리자 인증이 필요합니다. 서버에 등록된 관리자 토큰으로 로그인한 뒤 조회하세요.');}
  };
  const test=async(id:string)=>{
    setBusy(id);setError('');
    try{const r=await apiClient.post(`${API_BASE_URL}/integrations/${encodeURIComponent(id)}/test`);setResults(old=>({...old,[id]:r.data}));}
    catch{setError('시험을 수행하지 못했습니다. 관리자 권한과 서버 연결 설정을 확인하세요.');}
    finally{setBusy('');}
  };
  return <section className="bg-white border rounded-xl p-5 mb-6 space-y-3">
    <h2 className="text-xl font-bold">관리자 · 데이터 소스 연결 시험</h2>
    <p className="text-sm text-slate-600">운영 DB·Parquet·검증표의 연결과 읽기 응답을 확인합니다. 시험 성공은 실시간 수집 시작이나 데이터 승인이 아닙니다. 추가 DB의 인증정보는 서버에서 관리합니다.</p>
    <button className="border rounded px-4 py-2" onClick={()=>void load()}>등록 소스 조회</button>
    {error&&<p role="alert" className="text-red-700">{error}</p>}
    {sources.map(s=><div key={s.id} className="border rounded p-3"><div className="flex gap-4 items-center"><b>{s.label}</b><span>{s.mode} · {s.configured?'설정됨':'설정 필요'}</span><button disabled={!!busy||!s.configured} className="border rounded px-3 py-1" onClick={()=>void test(s.id)}>{busy===s.id?'확인 중…':'읽기 연결 시험'}</button></div>{results[s.id]&&<pre className="text-xs whitespace-pre-wrap mt-2">{JSON.stringify(results[s.id],null,2)}</pre>}</div>)}
  </section>;
}
