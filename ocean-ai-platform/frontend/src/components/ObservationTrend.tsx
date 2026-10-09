import {observationPlot} from '../data/observationSeries';

/** A small plot of the actual 24 raw records, with missing samples left as gaps. */
export default function ObservationTrend({rows,label,item=''}:{rows:any[];label:string;item?:string}) {
  const plot=observationPlot(rows,item,136,32);
  if(!plot.numericCount)return <p className="obs-no-trend">수치 자료 없음</p>;
  return <svg viewBox="0 0 140 40" className="obs-trend" role="img" aria-label={label+' 최근 '+plot.samples.length+'건의 원천 관측시각별 '+(plot.direction?'개별값':'추세')}>
    <g transform="translate(2,3)">
      {plot.segments.filter(segment=>segment.length>1).map((segment,i)=><path key={i} d={'M'+segment.map(p=>`${p.x},${p.y}`).join(' L')} fill="none" stroke="#1684ff" strokeWidth="1.5"/>)}
      {plot.points.filter(p=>p.x!==null&&p.y!==null).map(p=><circle key={p.key} cx={p.x!} cy={p.y!} r={plot.direction?1.7:1.2} fill="#1684ff"/>)}
    </g>
  </svg>;
}
