import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, Compass } from 'lucide-react';
import { menuPurposeFor, menuPurposes } from '../data/menuPurposes';
import { observationContext } from '../data/observationPeriod';
import ObservationPeriodNotice from './ObservationPeriodNotice';

export default function MenuPurpose(){
  const {pathname,search}=useLocation(),entry=menuPurposeFor(pathname);
  if(!entry)return null;
  const context=observationContext(new URLSearchParams(search));
  const query=context.size?`?${context}`:'';
  // The observation workspace has its own period and task controls beside the map.
  if(pathname==='/observations')return null;
  const basis=entry.basis==='daily'?'업무매뉴얼 제2장 PDF 2–3쪽: 일일점검 → 이상·조치 보고 → 점검 결과 확인'
    :entry.basis==='quality'?'품질관리 가이드북(2023.12) PDF 15·22·35–36쪽: 자동검사와 수동 최종판정 구분'
      :'프로젝트 업무 역할 계약에 따른 화면 구성 제안';
  return <section aria-label={`${entry.name} 업무 안내`} className="mx-4 mt-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2"><Compass aria-hidden="true" className="h-4 w-4 shrink-0 text-blue-600"/><p className="text-xs font-medium leading-relaxed text-slate-700">{entry.purpose}</p></div>
      <nav aria-label="다음 업무" className="flex flex-wrap items-center gap-2">{entry.next.map(path=><Link key={path} to={path+query} className="inline-flex items-center gap-1.5 rounded-md border border-blue-100 px-2.5 py-1.5 text-[11px] font-medium text-blue-800 hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">{menuPurposes[path].name}<ArrowRight aria-hidden="true" className="h-3 w-3"/></Link>)}</nav>
    </div>
    <ObservationPeriodNotice />
    <details key={pathname} className="mt-2 text-xs text-slate-600"><summary className="w-fit cursor-pointer rounded text-[11px] text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">현재 기능과 업무 범위</summary>
      <dl className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">{[['활용 역할',entry.role],['업무 입력',entry.input],['현재 가능한 행동',entry.action],['확인할 산출물',entry.output]].map(([label,value])=><div key={label}><dt className="font-semibold text-slate-700">{label}</dt><dd className="mt-1 leading-relaxed">{value}</dd></div>)}</dl>
      <p className="mt-3 rounded-lg bg-slate-50 p-2.5 leading-relaxed"><span className="mr-2 font-semibold text-slate-700">남은 연결·검증</span>{entry.pending}</p>
      <p className="mt-3 text-[11px] leading-relaxed text-slate-500">근거: {basis}. 매뉴얼의 당시 조직과 현재 계정 권한은 별도입니다. 이 안내는 승인 권한을 부여하지 않습니다.</p>
    </details>
  </section>;
}
