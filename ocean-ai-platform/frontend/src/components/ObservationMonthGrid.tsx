import {observationAvailability} from '../data/observationAvailability';

export default function ObservationMonthGrid({rows,from,to,onMonth}:{rows:any[];from:string;to:string;onMonth?:(month:string)=>void}) {
  const cells=observationAvailability(rows,from,to);
  return <div className="space-y-2">
    <div className="flex flex-wrap justify-between gap-2 text-xs"><span className="font-semibold">월별 자료 유무</span><span className="text-slate-500">자료 있는 월 {cells.filter(c=>c.held).length}/{cells.length} · 파랑: 자료 있음 · 회색: 자료 없음</span></div>
    <div className="flex flex-wrap gap-1.5">{cells.map(cell=><button key={cell.month} type="button" disabled={!onMonth} onClick={()=>onMonth?.(cell.month)} aria-label={cell.month+' '+(cell.held?'자료 있음':'자료 없음')}
      className={'rounded-md border px-2 py-1.5 text-[11px] font-medium focus-visible:outline-2 focus-visible:outline-blue-600 '+(cell.held?'bg-blue-50 border-blue-200 text-blue-800':'bg-slate-50 border-slate-200 text-slate-500')}>{cell.month.slice(2).replace('-','.')}</button>)}</div>
    <p className="text-[11px] text-slate-500">자료가 없는 월은 보유 자료의 공백입니다. 실제 관측 중단 여부는 별도 이력에서 확인합니다.</p>
  </div>;
}
