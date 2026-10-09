import {useState} from 'react';
import {observationPlot,observationSeriesUnit} from '../data/observationSeries';

const WIDTH=1000,HEIGHT=235,LEFT=68,TOP=28,PLOT_WIDTH=912,PLOT_HEIGHT=148;
const numberLabel=(value:number)=>new Intl.NumberFormat('ko-KR',{maximumFractionDigits:4}).format(value);
const clockLabel=(clock:number)=>new Date(Math.floor(clock/1000)).toISOString().slice(5,19).replace('T',' ');

/** Native-clock coordinates retain timing gaps and every duplicate source row. */
export default function ObservationSeriesChart({rows,item,label}:{rows:any[];item:string;label:string}) {
  const plot=observationPlot(rows,item,PLOT_WIDTH,PLOT_HEIGHT);
  const [chosen,setChosen]=useState<number|null>(null);
  const selectedIndex=chosen==null?Math.max(0,plot.samples.length-1):Math.min(chosen,plot.samples.length-1);
  const selected=plot.points[selectedIndex];
  const pick=(event:React.PointerEvent<SVGSVGElement>)=>{
    const rect=event.currentTarget.getBoundingClientRect();
    const x=(event.clientX-rect.left)*WIDTH/rect.width-LEFT;
    let best=-1,distance=Infinity;
    plot.points.forEach((point,index)=>{if(point.x===null)return;const next=Math.abs(point.x-x);if(next<=distance){best=index;distance=next;}});
    if(best>=0)setChosen(best);
  };
  if(!plot.numericCount)return <p role="status" className="obs-chart-empty">{rows.length?'그릴 수 있는 수치·관측시각 쌍이 없습니다. 원천 기록은 표에서 확인할 수 있습니다.':'선택 조건에 관측자료가 없습니다.'}</p>;
  return <div className="obs-series-chart">
    <div className="obs-chart-viewport"><svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} onPointerMove={pick} onPointerLeave={()=>setChosen(null)} role="img" aria-label={`${label} ${plot.samples.length}건, 원문 관측시각에 따른 실제 ${plot.direction?'개별 관측값':'시계열'}`}>
      <text x={LEFT} y="15" className="obs-chart-axis-title">{observationSeriesUnit(rows)}</text>
      {[0,.25,.5,.75,1].map(fraction=>{
        const y=TOP+PLOT_HEIGHT*fraction;
        return <g key={fraction}><line x1={LEFT} x2={LEFT+PLOT_WIDTH} y1={y} y2={y} className="obs-chart-grid"/><text x={LEFT-10} y={y+4} textAnchor="end" className="obs-chart-label">{numberLabel(plot.high-(plot.high-plot.low)*fraction)}</text></g>;
      })}
      {[0,.25,.5,.75,1].filter(fraction=>plot.first!==plot.last||fraction===.5).map(fraction=>{
        const x=LEFT+PLOT_WIDTH*fraction;
        return <g key={fraction}><line x1={x} x2={x} y1={TOP} y2={TOP+PLOT_HEIGHT} className="obs-chart-grid vertical"/><text x={x} y={TOP+PLOT_HEIGHT+23} textAnchor={fraction===0?'start':fraction===1?'end':'middle'} className="obs-chart-label">{clockLabel(plot.first+(plot.last-plot.first)*fraction)}</text></g>;
      })}
      <g transform={`translate(${LEFT},${TOP})`}>
        {plot.segments.filter(segment=>segment.length>1).map((segment,i)=><path key={i} d={'M'+segment.map(p=>`${p.x},${p.y}`).join(' L')} className="obs-chart-line"/>)}
        {plot.points.filter(point=>point.x!==null&&point.y!==null).map(point=><circle key={point.key} cx={point.x!} cy={point.y!} r={plot.direction?3:2} className="obs-chart-point"><title>{point.time+' · '+String(point.raw)+' · '+point.filename+' #'+String(point.rowNumber)}</title></circle>)}
        {selected?.x!=null&&<line x1={selected.x} x2={selected.x} y1="0" y2={PLOT_HEIGHT} className="obs-chart-crosshair"/>}
        {selected?.x!=null&&selected.y!=null&&<circle cx={selected.x} cy={selected.y} r="5" className="obs-chart-selected"/>}
      </g>
      <text x={LEFT+PLOT_WIDTH} y={HEIGHT-4} textAnchor="end" className="obs-chart-axis-title">원문 관측시각</text>
    </svg></div>
    <div className="obs-chart-selection" aria-live="polite"><time>{selected?.time.replace('T',' ')||'관측시각 없음'}</time><strong>{selected?.raw==null||String(selected.raw).trim()===''?'값 없음':String(selected.raw)} <small>{selected?.unit||'원천값'}</small></strong><span title={selected?.filename}>{selected?.filename.split(/[\\/]/).at(-1)} · 행 {String(selected?.rowNumber??'—')}{selected?.depth.some(value=>value!=null)?' · 수심 '+selected.depth.map(value=>value??'—').join('/') : ''}</span></div>
    <label className="obs-chart-scrubber">관측 기록 선택 <input type="range" min="0" max={Math.max(0,plot.samples.length-1)} value={selectedIndex} onChange={event=>setChosen(Number(event.target.value))} aria-label={label+' 그래프 관측 기록 선택'}/><span>{selectedIndex+1} / {plot.samples.length}건</span></label>
    <p className="obs-chart-note">수치 {plot.numericCount}건{plot.missingCount?' · 값 없음/비수치 '+plot.missingCount+'건':''}{plot.invalidClockCount?' · 시각 해석 불가 '+plot.invalidClockCount+'건':''}{plot.coincident?' · 동일 시각 원천 '+plot.coincident+'건 (각 기록 보존)':''}{plot.direction?' · 방향값은 개별 점으로 표시':''}</p>
  </div>;
}
