// File-lake scope is independent of PostgreSQL's operational dashboard.
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { API_BASE_URL, apiClient } from '../api/client';
import TechnicalReviewReceipt from './TechnicalReviewReceipt';

export default function FoundationLake() {
  const {search}=useLocation();
  const context=new URLSearchParams(search);
  const rawSources=['GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST'];
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [source, setSource] = useState('');
  const [month, setMonth] = useState('');
  const [station, setStation] = useState('');
  const [item, setItem] = useState('');
  const [sample, setSample] = useState<any>(null);
  const [channels, setChannels] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [channelSnapshot,setChannelSnapshot]=useState('');
  const requestSequence=useRef(0);
  useEffect(()=>{
    requestSequence.current+=1;setSample(null);setChannels([]);setChannelSnapshot('');setBusy(false);
  },[source,month,station,item]);
  useEffect(()=>{
    const params=new URLSearchParams(search), selected=params.get('source')||'';
    setSource(['GD_OBS_BU','GD_OBS_VBU','GR_OBS_ST'].includes(selected)?selected:'');
    setMonth(params.get('to')||'');setStation(params.get('station')||'');setItem(params.get('item')||'');
    setSample(null);setChannels([]);setChannelSnapshot('');
  },[search]);
  useEffect(() => {
    const load = () => apiClient.get(`${API_BASE_URL}/data-lake/foundation/summary`).then(r => { setData(r.data); setError(''); }).catch(() => {setData(null);setError('파일 레이크 현황을 읽지 못했습니다. 서버와 레이크 경로를 확인하세요.');});
    void load(); const timer = setInterval(() => void load(), 30000); return () => clearInterval(timer);
  }, []);
  const query = async () => {
    if(!source||!month||!station.trim()||!item.trim()){setError('원천·월·관측소·항목을 선택하거나 입력하세요.');return;}
    const requestId=++requestSequence.current;
    setBusy(true); setError(''); setSample(null); setChannels([]);setChannelSnapshot('');
    try {
      const [raw, validation] = await Promise.all([
        apiClient.get(`${API_BASE_URL}/data-lake/foundation/observations`, { params: { source, month:month.replace('-',''), station:station.trim(), item:item.trim(), limit: 100 } }),
        apiClient.get(`${API_BASE_URL}/data-lake/foundation/channels`, { params: { station, item } })
      ]);
      if(requestId!==requestSequence.current)return;
      setSample(raw.data); setChannels(validation.data.channels.filter((r: any) => r.source_group === source));
      setChannelSnapshot(validation.data.snapshot||'응답에 검증본 식별자가 없습니다.');
    } catch { if(requestId===requestSequence.current)setError('조회 실패: 원천·월·코드와 파일 검증 상태를 확인하세요.'); }
    finally { if(requestId===requestSequence.current)setBusy(false); }
  };
  return <section className="mt-6 space-y-4">
    <h2 className="text-xl font-bold">월별자료 · 파일 레이크 검증</h2>
    <p className="border border-amber-200 bg-amber-50 p-4 rounded">월별 원천에서 변환한 Parquet를 조회합니다. 변환 완료는 원본 CSV의 현재 보존, 센서·단위·시간대·QC 승인이나 학습 데이터셋 확정을 뜻하지 않습니다. 원천별 중복 가능성이 있어 행 수를 유일 관측 건수로 합산하지 않습니다.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {data ? <div className="bg-white border rounded-xl p-5 space-y-2">
      <p>추가 파일 {data.verified_monthly_files}/99개 변환·정산 완료 · {data.conversion.state}</p>
      {data.source_availability ? <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm">
        <p>원본 CSV 현재 위치 확인: 이전 기록과 크기·수정시각 일치 {data.source_availability.counts.METADATA_MATCH_NOT_REHASHED || 0}/{data.source_availability.total}개 · 경로에 없음 {data.source_availability.counts.MISSING || 0}개 · 변경·접근 오류·위치 미확정 {Object.entries(data.source_availability.counts).reduce((n:number,[state,count]:[string,any])=>n+(state==='MISSING'||state==='METADATA_MATCH_NOT_REHASHED'?0:Number(count)),0)}개</p>
        <p className="mt-1">현재 원본 전체 해시는 재검사하지 않았습니다. Parquet 보유와 원본 파일 보존은 별도이며, Parquet만으로 동일한 원본 CSV 파일을 복원했다고 판단하지 않습니다.</p>
      </div> : <p className="text-sm text-slate-500">원본 CSV의 현재 보존 여부 미조회</p>}
      <table className="w-full text-left"><thead><tr><th>원천</th><th>파일</th><th>보유 행</th></tr></thead><tbody>{data.monthly_groups.map((g: any) => <tr key={g.source}><td>{g.source}</td><td>{g.files}</td><td>{g.rows.toLocaleString()}</td></tr>)}</tbody></table>
      <p>검증표: 기존 Parquet {data.validation.baseline_files.toLocaleString()}개 + 추가 파일 {data.validation.new_monthly_verified_files}개 반영</p>
      <p className="text-sm text-slate-600">검증표 기준 {data.validation.at}. 원천 변환과 검증표 갱신 시각은 별개입니다.</p>
      <p>확대 문서 처리 {data.document_extraction?.completed ?? 0}/{data.document_extraction?.total ?? 0} · {data.document_extraction?.state ?? '미확인'} · 추출과 내용 검토는 별도</p>
    </div> : !error && <p>조회 중…</p>}
    <TechnicalReviewReceipt />
    <div className="bg-white border rounded-xl p-5 space-y-3"><h3 className="font-bold">추가 월별 Parquet 원천 조회</h3>
      <p className="text-sm">파일 순서로 최대 100행. 원천 QC·수층을 유지하며 단위·시간대를 임의 변환하지 않습니다.</p>
      <p className="text-xs text-slate-600">이 조회는 추가 월별 원천의 개별 표본 점검입니다. 상단 전체 집계 및 기준자료 지도와 별도이며, 월·관측소·항목을 명시해 실행합니다. {context.get('source')&&!rawSources.includes(context.get('source')!)?'현재 선택한 자료는 이 표본 API의 지원 원천이 아닙니다. 아래에서 별도 원천을 선택하세요.':''}</p>
      <div className="flex flex-wrap gap-3">
        <label>원천 <select className="border p-2" value={source} onChange={e => {setSource(e.target.value);setSample(null);setChannels([]);setChannelSnapshot('');}}><option value="">원천 선택</option>{rawSources.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>월 <input type="month" className="border p-2" value={month} onChange={e => setMonth(e.target.value)} /></label>
        <label>관측소 <input className="border p-2 w-32" value={station} onChange={e => setStation(e.target.value)} /></label>
        <label>항목 <input className="border p-2" value={item} onChange={e => setItem(e.target.value)} /></label>
        <button disabled={busy||!source||!month||!station.trim()||!item.trim()} className="rounded bg-blue-600 text-white px-4 py-2 disabled:opacity-50" onClick={() => void query()}>{busy ? '조회 중…' : '원천·검증 조회'}</button>
      </div>
      {channelSnapshot&&<p className="text-xs text-slate-600">연결 검증본: {channelSnapshot} · 아래 채널 요약은 해당 원천·관측소·항목의 전체 보유기간이며, 표본은 선택한 한 달입니다. 시설 연결본과 검증본 ID가 다르면 같은 버전으로 간주하지 않습니다.</p>}
      {channels.map((c: any, n: number) => <div key={n} className="border rounded p-3"><b>{c.station_name} · {c.item_labels}: {c.overall_display}</b><p>관측소 코드 {c.condition_decisions.station_dictionary_decision} / 항목 코드 {c.condition_decisions.item_dictionary_decision} / 센서 {c.condition_decisions.sensor_decision}</p><p>QC 사건 연결 {c.linked_qc_event_month_count}/{c.held_month_count}개월 · QC 승인과 별개</p></div>)}
      {sample && <><p>{sample.returned_rows}행 조회 · 원천층 · 미승인</p><div className="overflow-auto max-h-96"><table className="text-xs w-full text-left"><thead><tr>{Object.keys(sample.rows[0] || {}).map(k => <th className="p-2 border-b" key={k}>{k}</th>)}</tr></thead><tbody>{sample.rows.map((r: any, i: number) => <tr key={i}>{Object.values(r).map((value: any, j: number) => <td className="p-2 border-b whitespace-nowrap" key={j}>{value == null ? '미확정' : String(value)}</td>)}</tr>)}</tbody></table></div></>}
    </div>
  </section>;
}
