// 파일 역할: 모델·데이터셋 버전과 학습·배포 상태를 표시합니다.
import { API_BASE_URL } from '../api/client';
import TrainingWorkbench from '../components/TrainingWorkbench';
import { observationContext, observationPeriod } from '../data/observationPeriod';
import React, { useState, useEffect, useRef } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { apiClient as axios } from '../api/client';
import { 
  Box, CheckCircle, Clock, RefreshCw, Activity,
  Search, ChevronRight,
  Filter, Download, Plus, DownloadCloud, Play, FileText,
  Info
} from 'lucide-react';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, ComposedChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, CartesianGrid
} from 'recharts';

const MLOps: React.FC = () => {
  const {search}=useLocation();
  const scope=new URLSearchParams(search);
  const context=observationContext(scope);
  const period=observationPeriod(scope);
  const contextQuery=context.size?`?${context}`:'';
  const [query,setQuery]=useState(''),[targetFilter,setTargetFilter]=useState(''),[statusFilter,setStatusFilter]=useState('');
  const [loading,setLoading]=useState(true),busy=useRef(false);
  const [counts,setCounts]=useState<Record<string,number>|null>(null);
  const [modelList, setModelList] = useState<any[]>([]);
  const [retrainHistory, setRetrainHistory] = useState<any[]>([]);
  const [totalModels, setTotalModels] = useState<number | null>(null);
  const [statusData, setStatusData] = useState<any[]>([]);
  const [loadError,setLoadError] = useState('');
  const [pendingApprovals,setPendingApprovals] = useState<any[]>([]);
  const [checkedAt,setCheckedAt] = useState('');
  const [causeData, setCauseData] = useState<any[]>([]);
  const [perfTrendData, setPerfTrendData] = useState<any[]>([]);
  const [readiness, setReadiness] = useState<any>(null);
  const [adapterCoverage,setAdapterCoverage] = useState<any>(null);
  const [adapterError,setAdapterError] = useState('');

  const fetchData = async (signal:AbortSignal) => {
    if(busy.current)return;
    busy.current=true;setLoading(true);setLoadError('');setAdapterError('');
    try {
      const [sumRes,histRes,approvals,adapters]=await Promise.all([
        axios.get(`${API_BASE_URL}/mlops/summary`,{signal}),
        axios.get(`${API_BASE_URL}/mlops/retrain-history`,{signal}),
        axios.get(`${API_BASE_URL}/approvals/pending`,{signal}),
        axios.get(`${API_BASE_URL}/mlops/adapters`,{signal}).catch(()=>null)]);
      if(signal.aborted)return;
      if(!Array.isArray(sumRes.data.models)||!Array.isArray(histRes.data.history)||!Array.isArray(approvals.data.approvals))throw new Error('응답 형식 미확인');
      if(adapters&&Array.isArray(adapters.data.rows)&&Number.isInteger(adapters.data.task_keys)&&adapters.data.task_keys===adapters.data.rows.length){setAdapterCoverage(adapters.data);}
      else {setAdapterCoverage(null);setAdapterError('업무별 코드 범위 조회 실패 · 이전 값은 표시하지 않습니다.');}
      setPendingApprovals(approvals.data.approvals.filter((r:any)=>r.target_type==='MODEL_DEPLOY').map((r:any)=>({icon:<FileText className="w-4 h-4"/>,title:'모델 배포 검토',sub:`${r.data.model_name} (${r.target_id})`,user:'검토자 미지정',time:'',tag:r.status,tagColor:'text-amber-700'})));
      setCheckedAt(new Date().toLocaleString('ko-KR'));
      const st = sumRes.data.counts;
      setReadiness(sumRes.data.readiness??null);setCounts(st);
      const total = sumRes.data.total;
      setTotalModels(sumRes.data.total);
      const statusNames:Record<string,string>={ACTIVE:'활성 기록',VALIDATING:'검증 기록',RETRAIN_REQUIRED:'재학습 필요',PENDING_APPROVAL:'승인 대기',ARCHIVED:'보관',PRODUCTION:'운영 등록',RETRAINING:'재학습 기록',APPROVED:'승인 기록'};
      const statusColors=['#3B82F6','#64748B','#D97706','#8B5CF6','#0E7490'];
      setStatusData(Object.entries(st).filter(([,value])=>typeof value==='number'&&value>0).map(([key,value],index)=>({name:statusNames[key]||key,value,percent:total>0?`${Math.round(Number(value)/total*100)}%`:'분모 없음',color:statusColors[index%statusColors.length]})));

      const mappedModels = sumRes.data.models.map((m: any) => ({
        id: m.model_id,
        name: m.name,
        version: m.version,
        target: m.target,
        registryStatus:m.status,
        range: '범위 미검증',
        status: m.readiness?.operational_verified ? '운영 검증됨' : m.deployment_status === 'PRODUCTION' ? '운영 기록 · 실행 미검증' : m.status === 'VALIDATING' ? '검증중' : m.status === 'RETRAINING' ? '재학습중' : m.status === 'RETRAIN_REQUIRED' ? '재학습 필요' : m.status,
        statusColor: m.readiness?.operational_verified ? 'text-emerald-600' : 'text-amber-700',
        date: m.deployed_at ? `${new Date(m.deployed_at).toLocaleString('ko-KR')} · 기록` : '기록 없음',
        perf: m.metrics ? `F1 ${m.metrics.F1 ?? m.metrics.f1 ?? '-'} / RMSE ${m.metrics.RMSE ?? m.metrics.rmse ?? '-'}` : '',
        deploy: m.readiness?.operational_verified ? '배포 검증됨' : '배포 보류',
        deployColor: m.readiness?.operational_verified ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : 'text-amber-600 bg-amber-50 border-amber-200'
      }));
      setModelList(mappedModels);

      const mappedHist = histRes.data.history.map((h: any) => ({
        id: h.training_id,
        model: h.model_name,
        range: '범위 미검증',
        perf: h.performance_before && h.performance_after ? `${h.performance_before.F1 ?? h.performance_before.f1 ?? '-'} → ${h.performance_after.F1 ?? h.performance_after.f1 ?? '-'}` : '-',
        status: h.status === 'COMPLETED' ? '종료 기록 · 실행 검증 별도' : h.status,
        statusColor: h.status === 'COMPLETED' ? 'text-slate-600 bg-slate-50 border-slate-200' : 'text-amber-600 bg-amber-50 border-amber-200'
      }));
      setRetrainHistory(mappedHist);
      
      setPerfTrendData(sumRes.data.perfTrendData || []);
      const totalCause = (sumRes.data.causeData || []).reduce((acc: number, cur: any) => acc + cur.count, 0);
      const colors = ['#6366F1', '#3B82F6', '#10B981', '#F59E0B', '#EF4444'];
      setCauseData((sumRes.data.causeData || []).map((d: any, i: number) => ({
        name: d.cause || '원인 미상',
        value: d.count,
        percent: totalCause > 0 ? ((d.count / totalCause) * 100).toFixed(1) + '%' : '0%',
        color: colors[i % colors.length]
      })));
      
    } catch (e) {
      if(signal.aborted)return;
      setCounts(null);
      setReadiness(null);
      setAdapterCoverage(null);setAdapterError('');
      setPendingApprovals([]); setCheckedAt(''); setLoadError('모델 등록부 조회 실패 · 이전 값은 표시하지 않습니다.'); setTotalModels(null); setStatusData([]); setModelList([]); setPerfTrendData([]); setCauseData([]); setRetrainHistory([]);
    } finally {busy.current=false;if(!signal.aborted)setLoading(false);}
  };

  useEffect(() => {
    const abort=new AbortController();
    fetchData(abort.signal);
    const interval = setInterval(()=>fetchData(abort.signal), 60000);
    return () => {abort.abort();busy.current=false;clearInterval(interval);};
  }, []);

  const handleRetrain = () => document.getElementById('training-input-review')?.scrollIntoView({behavior:'smooth',block:'start'});

  const mlopsAlerts: any[] = [];
  const filteredModels=modelList.filter(row=>(!targetFilter||row.target===targetFilter)&&(!statusFilter||row.registryStatus===statusFilter)&&`${row.name} ${row.target} ${row.version}`.toLowerCase().includes(query.trim().toLowerCase()));
  const unknown=loadError?'조회 실패':loading?'조회 중':'미확인';
  const execution=readiness?.execution;
  const workerLabels:Record<string,string>={RUNNING:'실행 프로세스 확인',NOT_CONFIGURED:'학습 사용 미설정',STALE_OR_CHANGED:'프로세스·코드 또는 하트비트 재확인 필요',EVIDENCE_INVALID:'프로세스 검증 근거 오류'};
  const deploymentLabel=readiness?.operational_model_count>0?'로컬 운영 검증됨':readiness?.ready_for_deployment?'승인 후보 · 배포 결정 필요':'배포 보류';
  const hasPerformance=perfTrendData.some(row=>row.f1!=null||row.rmse!=null);
  const exportRegistry=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({scope:'GLOBAL_REGISTRY',checked_at:checkedAt,models:filteredModels,readiness,adapter_coverage:adapterCoverage},null,2)],{type:'application/json'}));const anchor=document.createElement('a');anchor.href=url;anchor.download='model-registry-review.json';anchor.click();URL.revokeObjectURL(url);};

  return (
    <div className="p-4 md:p-6 space-y-4 bg-[#F8FAFC] min-h-full font-sans overflow-x-hidden">
      {loadError && <p role="alert" className="text-red-700 text-sm">{loadError}</p>}
      <TrainingWorkbench workerConfigured={readiness?.execution?.worker_configured===true} models={modelList}/>
      {/* Top Header */}
      <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-slate-900">모델 관리 (MLOps)</h2>
            <span className="text-sm text-slate-500 font-medium ml-2">AI 모델의 학습, 검증, 배포, 성능 모니터링, 재학습 이력을 통합 관리합니다.</span>
          </div>
        </div>
        
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <span role="status" className="text-slate-500 font-medium">{loading?(checkedAt?`갱신 중 · 직전 확인 ${checkedAt}`:'조회 중'):loadError?'조회 실패':checkedAt?`조회 확인 ${checkedAt}`:'미조회'}</span>
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text"
              aria-label="모델명·항목·버전 검색" value={query} onChange={event=>setQuery(event.target.value)}
              placeholder="모델명, 대상 항목, 버전 검색" 
              className="pl-9 pr-4 py-2 border border-slate-200 rounded-md bg-white text-sm w-48 lg:w-64 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
            />
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">등록부 조회 · 승인 권한 별도</span>
        </div>
      </div>

      <p className="text-xs leading-relaxed text-slate-500">관측 조회 문맥: {period.source} · {period.from} ~ {period.to} · 관측망 {scope.get('network')||'전체'} · 해역 {scope.get('sea')||'전체'}. 아래 모델·평가·승인 건수는 이 필터와 별도의 전체 등록부입니다.</p>
      <section aria-label="운영 준비 검증" className="bg-white border border-slate-200 rounded-xl p-4 text-sm text-slate-700">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold text-slate-800">운영 준비 검증</h3><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${loadError?'bg-red-50 text-red-700':readiness?.operational_model_count>0?'bg-emerald-50 text-emerald-800':readiness?'bg-amber-50 text-amber-800':'bg-slate-100 text-slate-600'}`}>{readiness?deploymentLabel:unknown}</span></div>
        {readiness && <>
          <p className="mt-1">등록 모델 {readiness.counts.models}개 · 데이터셋 {readiness.counts.datasets}개 · 승인 상태 데이터셋 {readiness.counts.approved_datasets}개 · 실제 운영 검증 모델 {readiness.operational_model_count}개</p>
          {execution?<>
            <p className="mt-1">학습·검증 실행 코드: {execution.code_implemented===true?'구현됨':'미확인'} · 학습 프로세스: {workerLabels[execution.worker_status]??'미확인'}{execution.worker_running===true&&typeof execution.worker_pid==='number'?` (PID ${execution.worker_pid})`:''} · 학습 사용 설정: {execution.worker_configured===true?'설정됨':execution.worker_configured===false?'미설정':'미확인'}</p>
            <p className="mt-1">승인된 실제 학습 입력: {execution.approved_input_ready===true?'검증 통과':execution.approved_input_ready===false?'승인·입력 검증 필요':'미확인'} · 로컬 서빙 사용 설정: {execution.serving_configured===true?'설정됨':execution.serving_configured===false?'미설정':'미확인'} · 실제 로컬 서빙 검증 모델: {typeof execution.live_local_model_count==='number'?`${execution.live_local_model_count}개`:'미확인'}</p>
            <p className="mt-1">품질·지연·비용 합격 기준: {readiness.acceptance_criteria_status==='VERIFIED_PER_CANDIDATE'?'후보별 승인 검증 통과':'정의·승인 근거 확인 필요'}. 프로세스 실행과 코드 구현은 원천 승인·업무별 운영 모델 선정을 대신하지 않습니다.</p>
          </>:<p className="mt-1">현재 응답에 실행 환경 검증이 없습니다. 학습 프로세스의 실행 여부를 추정하지 않습니다.</p>}
          <details className="mt-2"><summary className="cursor-pointer text-xs font-medium text-blue-700">누락 근거와 모델별 검증 내역</summary><ul className="mt-2 list-disc pl-5">{readiness.blockers.map((item:any)=><li key={item.code}>{item.message}</li>)}</ul>
          {readiness.models.map((item:any)=><details key={item.model_version} className="mt-2">
            <summary className="cursor-pointer font-medium">{item.model_version} · 배포 보류 근거 {item.blockers.length}건</summary>
            <ul className="mt-1 list-disc pl-5">{item.blockers.map((block:any)=><li key={block.code}>{block.message}</li>)}</ul>
          </details>)}
          </details><p className="mt-2 text-xs">승인 기록·평가 지표·파일 존재만으로 실제 학습, 배포 또는 운영을 확정하지 않습니다.</p>
        </>}
        {!readiness&&!loading&&!loadError&&<p className="mt-2 text-xs">현재 응답에 운영 준비 검증이 없습니다. 운영 모델 수를 0으로 추정하지 않습니다.</p>}
        {adapterCoverage&&<div className="mt-3 border-t border-slate-100 pt-2">
          <p>업무별 코드 범위: {adapterCoverage.task_keys}개 업무 키 · {adapterCoverage.code_implementations}개 자료 표현 처리 구현. 각 업무는 아래에 명시한 제한 범위의 기준·후보 알고리즘을 사용합니다.</p>
          <p className="mt-1 text-xs text-slate-500">실제 승인 원천에서의 비교 완료·운영 선정 여부는 별도 검증합니다. 코드 범위 개수만으로 가이드 전체 항목·전체 HF 유동장·전체 궤적의 운영 완료를 판단하지 않습니다.</p>
          <details className="mt-2"><summary className="cursor-pointer text-xs font-medium text-blue-700">업무별 표현·현재 학습 상태와 구현 제한</summary>
            <div className="overflow-auto"><table className="mt-2 w-full text-xs"><thead><tr><th className="text-left p-1">영역·항목</th><th className="text-left p-1">업무·표현</th><th className="text-left p-1">이 코드 범위에 연결된 근거</th></tr></thead><tbody>{adapterCoverage.rows.map((row:any)=><tr key={`${row.domain}/${row.item_id}/${row.task}`} className="border-t border-slate-100"><td className="p-1">{row.domain} · {row.item_id}</td><td className="p-1">{row.task} · {row.quantity_kind}<br/><span className="text-slate-500">{row.supported_scope}</span></td><td className="p-1">{row.training_status==='NOT_EXECUTED_ON_APPROVED_SOURCE'?'승인 원천 학습 근거 미연결':row.training_status}<br/>{row.operating_model_selected===true?'운영 모델 선정 근거 연결됨':'운영 모델 선정 근거 미연결'}</td></tr>)}</tbody></table></div>
          </details>
        </div>}
        {adapterError&&<p role="alert" className="mt-2 text-xs text-red-700">{adapterError}</p>}
        {!adapterCoverage&&!adapterError&&<p className="mt-2 text-xs text-slate-500">업무별 코드 범위: {loading?'조회 중':'미확인'}</p>}
      </section>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {[
          { title: '전체 모델 수', val: totalModels?.toString() ?? '—', unit: '개', icon: Box, color: 'text-blue-500', bg: 'bg-blue-50', diff: totalModels==null?unknown:'전체 등록부 기준', diffColor: 'text-slate-500' },
          { title: '운영 검증 모델', val: readiness?.operational_model_count==null?'—':String(readiness.operational_model_count), unit: '개', icon: Activity, color: 'text-slate-600', bg: 'bg-slate-100', diff: readiness?'실행 근거 기준':unknown, diffColor: 'text-slate-500' },
          { title: '검증 상태 모델', val: counts?.VALIDATING==null?'—':String(counts.VALIDATING), unit: '개', icon: Clock, color: 'text-amber-500', bg: 'bg-amber-50', diff: '등록 상태 기준', diffColor: 'text-slate-500' },
          { title: '재학습 필요 모델', val: counts?.RETRAIN_REQUIRED==null?'—':String(counts.RETRAIN_REQUIRED), unit: '개', icon: RefreshCw, color: 'text-amber-600', bg: 'bg-amber-50', diff: '등록 상태 기준', diffColor: 'text-slate-500' },
          { title: '최근 배포 성공률', val: '필요입력 없음', unit: '', icon: CheckCircle, color: 'text-slate-500', bg: 'bg-slate-100', diff: '기간·시도 ID·실제 완료/실패 receipt 원장 필요', diffColor: 'text-slate-500' },
          { title: '동일 평가범위 F1 평균', val: totalModels===0?'평가대상 없음':'필요입력 없음', unit: '', icon: Search, color: 'text-slate-600', bg: 'bg-slate-100', diff: '같은 과업·라벨·고정 split·평가 모집단 필요', diffColor: 'text-slate-500' },
        ].map((card, i) => (
          <div key={i} className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between">
            <div className="flex items-center gap-3 mb-2">
              <div className={`p-2 rounded-full ${card.bg}`}><card.icon className={`w-5 h-5 ${card.color}`} /></div>
              <span className="text-sm font-bold text-slate-700">{card.title}</span>
            </div>
            <div className="mt-2">
              <p className="text-2xl font-black text-slate-800 text-center">{card.val} <span className="text-sm font-normal text-slate-500">{card.unit}</span></p>
              <div className="flex justify-between items-center mt-3 pt-2 border-t border-slate-100 text-[10px]">
                <span className="text-slate-400">집계 기준</span>
                <span className={`font-bold ${card.diffColor}`}>{card.diff}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between bg-white p-3 rounded-lg border border-slate-200 shadow-sm text-xs font-medium text-slate-600 gap-3">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <span>집계 범위</span>
            <span className="border border-slate-200 px-3 py-1.5 rounded">전체 등록 이력</span>
          </div>
          <div className="flex items-center gap-2">
            <span>모델 유형</span>
            <span className="text-slate-400">분류 필터 미연결</span>
          </div>
          <div className="flex items-center gap-2">
            <span>대상 관측항목</span>
            <select aria-label="모델 대상 관측항목" value={targetFilter} onChange={event=>setTargetFilter(event.target.value)} className="border border-slate-200 px-3 py-1.5 rounded focus-visible:ring-2 focus-visible:ring-blue-500"><option value="">전체</option>{[...new Set(modelList.map(row=>row.target))].filter(Boolean).sort().map(target=><option key={target} value={target}>{target}</option>)}</select>
          </div>
          <div className="flex items-center gap-2">
            <span>등록 상태</span>
            <select aria-label="모델 등록 상태" value={statusFilter} onChange={event=>setStatusFilter(event.target.value)} className="border border-slate-200 px-3 py-1.5 rounded focus-visible:ring-2 focus-visible:ring-blue-500"><option value="">전체</option>{[...new Set(modelList.map(row=>row.registryStatus))].filter(Boolean).sort().map(status=><option key={status} value={status}>{status}</option>)}</select>
          </div>
          <div className="flex items-center gap-2">
            <span>관측소 범위</span>
            <span className="text-slate-400">적용 범위 미검증</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={()=>{setQuery('');setTargetFilter('');setStatusFilter('');}} className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800 px-2 py-1.5 mr-2"><Filter className="w-3.5 h-3.5"/> 표 필터 초기화</button>
          <button onClick={handleRetrain} title="고정 승인 입력 선택·검증으로 이동" className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 rounded font-bold">
            <Plus className="w-3.5 h-3.5"/> 학습 입력 검토 필요
          </button>
          <button onClick={exportRegistry} disabled={totalModels==null||loading} className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded font-bold hover:bg-blue-700 shadow-sm transition-colors disabled:bg-slate-200 disabled:text-slate-500 disabled:cursor-not-allowed">
            <Download className="w-3.5 h-3.5"/> 조회 결과 내보내기
          </button>
        </div>
      </div>

      {/* Row 1: 모델 운영 현황, 상태 분포, 원인 분석 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: 모델 운영 현황 테이블 */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[350px] flex flex-col">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-base font-bold text-slate-800">모델 등록·운영 검증 현황</h3>
          </div>
          <div className="flex-1 overflow-auto custom-scrollbar">
            <table className="w-full text-xs text-center min-w-[800px]">
              <thead className="text-slate-500 bg-slate-50 border-y border-slate-200">
                <tr>
                  <th className="py-2.5 px-2 font-medium text-left">모델명</th>
                  <th className="py-2.5 px-2 font-medium">버전</th>
                  <th className="py-2.5 px-2 font-medium">대상 항목</th>
                  <th className="py-2.5 px-2 font-medium">적용 범위</th>
                  <th className="py-2.5 px-2 font-medium">운영 상태</th>
                  <th className="py-2.5 px-2 font-medium">등록된 배포 시각</th>
                  <th className="py-2.5 px-2 font-medium">성능 (F1 / RMSE)</th>
                  <th className="py-2.5 px-2 font-medium">배포 상태</th>
                  <th className="py-2.5 px-2 font-medium">작업</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {totalModels === 0 && <tr><td colSpan={9} className="py-8 text-slate-500">등록된 모델이 없습니다. 승인 데이터셋·평가·모델 파일 검증부터 필요합니다.</td></tr>}
                {totalModels==null&&<tr><td colSpan={9} className="py-8 text-slate-500">{unknown}</td></tr>}
                {totalModels!=null&&totalModels>0&&!filteredModels.length&&<tr><td colSpan={9} className="py-8 text-slate-500">현재 표 필터에 맞는 모델이 없습니다.</td></tr>}
                {filteredModels.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-2 text-left font-medium text-slate-800">{row.name}</td>
                    <td className="py-2.5 px-2 text-slate-500">{row.version}</td>
                    <td className="py-2.5 px-2 text-slate-600">{row.target}</td>
                    <td className="py-2.5 px-2 text-slate-600">{row.range}</td>
                    <td className={`py-2.5 px-2 font-bold ${row.statusColor}`}>{row.status}</td>
                    <td className="py-2.5 px-2 text-slate-500">{row.date}</td>
                    <td className="py-2.5 px-2 text-slate-600 text-[11px]">{row.perf}</td>
                    <td className="py-2.5 px-2">
                      <span className={`px-2 py-0.5 border rounded text-[10px] font-bold ${row.deployColor}`}>{row.deploy}</span>
                    </td>
                    <td className="py-2.5 px-2 text-slate-400 flex items-center justify-center gap-1.5">
                      <button onClick={handleRetrain} title="고정 승인 입력과 기준 모델을 선택하여 재학습 검토"><Play className="w-3.5 h-3.5" /></button>
                      <button disabled title="모델 파일 다운로드 미연결" aria-label="모델 파일 다운로드 미연결" className="cursor-not-allowed"><DownloadCloud className="w-3.5 h-3.5" /></button>
                      <Link to={`/data-lake${contextQuery}`} title="데이터셋 근거 확인" aria-label={`${row.name} 데이터셋 검토 화면`} className="hover:text-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500"><FileText className="w-3.5 h-3.5" /></Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between items-center mt-3 pt-3 border-t border-slate-100 text-xs">
            <span className="text-slate-500">{totalModels==null?unknown:`표 ${filteredModels.length}건 / 전체 등록 ${totalModels}건`}</span>
            <span className="text-slate-400">현재 응답 전체 · 카드와 차트는 전역 집계</span>
          </div>
        </div>

        {/* Right Stack */}
        <div className="flex flex-col gap-4 h-[350px]">
          {/* Donut Chart */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex-1 flex flex-col min-h-0">
            <h3 className="text-sm font-bold text-slate-800 mb-1">모델 등록 상태 분포</h3>
            <div className="flex-1 flex items-center justify-between">
              <div className="w-1/2 h-full relative flex justify-center items-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={statusData} innerRadius={35} outerRadius={55} dataKey="value" stroke="none">
                      {statusData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute text-center flex flex-col items-center justify-center">
                  <p className="text-[9px] text-slate-500">총 모델 수</p>
                  <p className="text-sm font-black text-slate-800">{totalModels==null?'—':`${totalModels}개`}</p>
                </div>
              </div>
              <div className="w-1/2 pl-2 space-y-1.5">
                {!statusData.length&&<p className="text-xs text-slate-500">{totalModels===0?'등록 없음 · 비율 분모 없음':unknown}</p>}
                {statusData.map((item, i) => (
                  <div key={i} className="flex justify-between items-center text-[10px]">
                    <div className="flex items-center gap-1.5 w-16">
                      <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: item.color }}></div>
                      <span className="text-slate-600 font-medium">{item.name}</span>
                    </div>
                    <div className="text-right flex-1">
                      <span className="font-bold text-slate-800">{item.value} </span>
                      <span className="text-slate-400 text-[9px]">({item.percent})</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          
          {/* Bar Chart */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex-1 flex flex-col min-h-0">
            <div className="flex justify-between items-center mb-1">
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-1">기록된 원인 후보 <Info className="w-3.5 h-3.5 text-slate-400"/></h3>
              <span className="text-[10px] text-slate-500">전체 예측 기록</span>
            </div>
            <div className="flex-1 overflow-auto space-y-1.5 mt-2">
              {!causeData.length&&<p className="text-xs text-slate-500">{totalModels==null?unknown:'원인 후보 기록 없음'}</p>}
              {causeData.map((item, i) => (
                <div key={i} className="flex items-center text-[10px]">
                  <span className="w-20 truncate text-slate-600">{item.name}</span>
                  <div className="flex-1 mx-2 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: item.percent, backgroundColor: item.color }}></div>
                  </div>
                  <span className="w-14 text-right font-medium text-slate-700">{item.value} <span className="text-slate-400">({item.percent})</span></span>
                </div>
              ))}
            </div>
            <div className="text-[10px] text-slate-500 mt-1 border-t border-slate-100 pt-1">
              후보 기록 건수 기준 · 확인 원인·모델 성능 저하의 증거는 별도
            </div>
          </div>
        </div>
      </div>

      {/* Row 2: 4 Columns Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* 1. 재학습 이력 */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[300px] flex flex-col">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-bold text-slate-800">재학습 이력</h3>
          </div>
          <div className="flex-1 overflow-auto">
            <table className="w-full min-w-[460px] text-[11px] text-center">
              <thead className="text-slate-400 border-b border-slate-100">
                <tr>
                  <th className="pb-2 font-medium text-left">training_id</th>
                  <th className="pb-2 font-medium">대상 모델</th>
                  <th className="pb-2 font-medium">데이터 범위</th>
                  <th className="pb-2 font-medium">성능 변화 <span className="font-normal">(F1 / RMSE)</span></th>
                  <th className="pb-2 font-medium">실행 기록</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 text-slate-600">
                {!retrainHistory.length&&<tr><td colSpan={5} className="py-6 text-center text-slate-500">{totalModels==null?unknown:'등록된 학습 이력 없음'}</td></tr>}
                {retrainHistory.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="py-2.5 text-left font-medium">{row.id}</td>
                    <td className="py-2.5 truncate max-w-[80px]" title={row.model}>{row.model}</td>
                    <td className="py-2.5">{row.range}</td>
                    <td className="py-2.5">{row.perf}</td>
                    <td className="py-2.5">
                      <span className={`px-1.5 py-0.5 border rounded font-bold ${row.statusColor}`}>{row.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between items-center mt-2 pt-2 border-t border-slate-100 text-[10px]">
            <span className="text-slate-500">{totalModels==null?unknown:`전체 ${retrainHistory.length}건`}</span>
            <span className="text-slate-400">실행 기록 · 승인 별도</span>
          </div>
        </div>

        {/* 2. 모델 성능 비교 */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[300px] flex flex-col">
          <div className="flex justify-between items-center mb-1">
            <h3 className="text-sm font-bold text-slate-800">모델 성능 비교</h3>
          </div>
          <div className="flex justify-between mb-2">
             <span className="text-[11px] text-slate-700 font-medium">기록된 학습 평가 이력</span>
             <span className="text-[10px] text-slate-500">F1 / RMSE</span>
          </div>
          <div className="flex items-center justify-center gap-4 text-[10px] mb-2 font-medium text-slate-600">
            <span className="flex items-center gap-1"><div className="w-2 h-0.5 bg-blue-500"></div> F1 Score</span>
            <span className="flex items-center gap-1"><div className="w-2 h-0.5 bg-emerald-500"></div> RMSE</span>
          </div>
          <div className="flex-1 w-full min-h-0 relative">
            {!hasPerformance?<div className="flex h-full items-center justify-center text-xs text-slate-500">{totalModels==null?unknown:'평가 지표 기록 없음'}</div>:<>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={perfTrendData} margin={{ top: 20, right: 0, left: -20, bottom: -10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="version" tick={{fontSize: 9, fill: '#64748B'}} stroke="#CBD5E1" axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" tick={{fontSize: 9, fill: '#64748B'}} stroke="#CBD5E1" axisLine={false} tickLine={false} domain={[0, 1]} />
                <YAxis yAxisId="right" orientation="right" tick={{fontSize: 9, fill: '#64748B'}} stroke="#CBD5E1" axisLine={false} tickLine={false} domain={[0, 'auto']} />
                <RechartsTooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #E2E8F0', borderRadius: '8px', fontSize: '11px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Line yAxisId="left" type="monotone" dataKey="f1" stroke="#3B82F6" strokeWidth={2} dot={{r:3}} label={{position: 'top', fontSize: 9, fill: '#3B82F6'}} />
                <Line yAxisId="right" type="monotone" dataKey="rmse" stroke="#10B981" strokeWidth={2} dot={{r:3}} label={{position: 'bottom', fontSize: 9, fill: '#10B981'}} />
              </ComposedChart>
            </ResponsiveContainer>
            </>}
          </div>
          <div className="text-center text-[10px] text-slate-500 mt-2">단위·지평·시험 멤버십 동등성 미검증 · 우수 모델 선정 아님</div>
        </div>

        {/* 3. 배포 및 승인 대기 */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[300px] flex flex-col">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-bold text-slate-800">배포 및 승인 대기</h3>
            <Link to={`/alerts${contextQuery}`} className="text-[10px] text-blue-700 flex items-center focus-visible:ring-2 focus-visible:ring-blue-500">검토 대상 보기 <ChevronRight className="w-3 h-3 inline"/></Link>
          </div>
          <div className="flex-1 overflow-auto space-y-3">
            {!pendingApprovals.length && checkedAt && <p className="text-xs text-slate-500">모델 배포 승인 대기 건이 없습니다.</p>}
            {!checkedAt&&<p className="text-xs text-slate-500">{unknown}</p>}
            {pendingApprovals.map((item, i) => (
              <div key={i} className="flex gap-2">
                <div className="mt-0.5 p-1.5 bg-slate-50 border border-slate-100 rounded-lg">{item.icon}</div>
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <span className="text-[11px] font-bold text-slate-800 leading-tight">{item.title}</span>
                    <span className={`px-1.5 py-0.5 border rounded text-[9px] font-bold ${item.tagColor}`}>{item.tag}</span>
                  </div>
                  <p className="text-[10px] text-slate-600 mt-0.5">{item.sub}</p>
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-[9px] text-slate-400">요청자: {item.user}</span>
                    <span className="text-[9px] text-slate-400">요청일: {item.time}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 4. 실시간 MLOps 알림 */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[300px] flex flex-col">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-bold text-slate-800">MLOps 감시 연결</h3>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">미연결</span>
          </div>
          <div className="flex-1 overflow-auto space-y-3.5">
            {!mlopsAlerts.length && <p className="text-xs text-slate-500">실시간 모델 감시·알림은 아직 연결되지 않았습니다.</p>}
            {mlopsAlerts.map((a, i) => (
              <div key={i} className="flex gap-2">
                <div className="mt-0.5">{a.icon}</div>
                <div className="flex-1 flex flex-col border-b border-slate-50 pb-2.5">
                  <div className="flex justify-between">
                    <span className="text-[11px] text-slate-700 font-bold">{a.text}</span>
                    <span className="text-[10px] text-slate-400 whitespace-nowrap">{a.time}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 mt-0.5">{a.sub}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MLOps;
