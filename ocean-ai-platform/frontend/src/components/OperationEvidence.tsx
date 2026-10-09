import {Activity} from 'lucide-react';
import {observationItemLabel} from '../data/observationAvailability';
import {validOperationEvidence,operatingState,observedAvailability,operationReasonText} from '../data/observationWorkspace';

const decimal=(value:unknown,suffix='')=>typeof value==='number'&&Number.isFinite(value)?new Intl.NumberFormat('ko-KR',{maximumFractionDigits:1}).format(value)+suffix:'—';
const qcLabel=(value:unknown)=>value==null?'NULL':String(value)===''?'빈 문자열':JSON.stringify(String(value));

export default function OperationEvidence({operation,expectedEnd}:{operation:any;expectedEnd:string}) {
  if(!validOperationEvidence(operation,expectedEnd))return <p className="obs-caption">기준시각과 일치하는 운영 진단 근거를 확인하지 못했습니다.</p>;
  const state=operatingState(operation,expectedEnd),channels=Array.isArray(operation.channels)?operation.channels:[];
  return <details className="obs-operation-evidence"><summary><Activity size={13}/>자료 기반 운영상태 · {state.label}<span>판정 근거</span></summary><div>
    <p className="obs-operation-reason">{operationReasonText(operation.reason||'채널별 최근 24시간 자료를 확인합니다.')}</p>
    <dl className="obs-operation-facts"><div><dt>참고 자료 채움</dt><dd>{observedAvailability(operation,expectedEnd)}</dd></div><div><dt>판정 채널</dt><dd>{operation.channels_evaluated??'—'} / {operation.channels_total??'—'}</dd></div></dl>
    <p className="obs-caption">{String(operation.window_start).replace('T',' ')} ~ {String(operation.window_end).replace('T',' ')}<br/>정책 {operation.policy_version}</p>
    {(operation.inspection_missing||operation.qc_interpretation_missing)&&<p className="obs-operation-limit">{operation.inspection_missing?'기준일 이전 점검 이력 없음. ':''}{operation.qc_interpretation_missing?'원문 QC 판본·의미 해석 확인 필요. ':''}장비 상태와 QC 승인은 별도 확인합니다.</p>}
    {Array.isArray(operation.not_evaluated)&&operation.not_evaluated.length>0&&<p className="obs-caption">미평가: {operation.not_evaluated.map(operationReasonText).join(' · ')}</p>}
    <div className="obs-channel-evidence">{channels.map((channel:any,index:number)=><details key={JSON.stringify([channel.item_code,channel.depth_step,channel.depth_from,channel.depth_to,index])}><summary>{observationItemLabel(channel.item_code)}{[channel.depth_step,channel.depth_from,channel.depth_to].some(d=>d!=null)?' · 수심 '+[channel.depth_step,channel.depth_from,channel.depth_to].map(d=>d??'—').join('/') : ''}<span>{({NORMAL:'정상',WARNING:'주의',ABNORMAL:'이상',UNVERIFIED:'확인 필요'} as Record<string,string>)[channel.state]||'확인 필요'}</span></summary><dl>
      <div><dt>최근 관측시각</dt><dd>{channel.last_clock?String(channel.last_clock).replace('T',' '):'자료 없음'}</dd></div><div><dt>기준시각 대비 지연</dt><dd>{decimal(channel.delay_seconds,'초')}</dd></div>
      <div><dt>추정 관측간격</dt><dd>{decimal(channel.cadence?.interval_seconds,'초')}</dd></div><div><dt>격자 대비 자료 채움</dt><dd>{decimal(channel.observed_grid?.availability_percent,'%')} ({channel.observed_grid?.held_slots??'—'} / {channel.observed_grid?.expected_slots??'—'})</dd></div>
      <div><dt>값 없음 / 비수치</dt><dd>{channel.missing_rows??'—'} / {channel.nonnumeric_rows??'—'}</dd></div><div><dt>중복 / 값 충돌</dt><dd>{channel.duplicate_rows??'—'} / {channel.duplicate_conflict_slots??'—'}</dd></div>
    </dl><p>{Array.isArray(channel.reasons)?channel.reasons.map(operationReasonText).join(' · '):''}</p>
    {Array.isArray(channel.qc_codes)&&<p className="obs-caption obs-operation-qc">원문 QC {channel.qc_codes.map((q:any)=>(q.field?({source_qc_raw:'QC',source_mq_raw:'MQ',source_n1_qc_raw:'N1 QC'} as Record<string,string>)[q.field]||q.field:'')+' '+qcLabel(Object.hasOwn(q,'literal')?q.literal:q.value)+' '+(q.count??0)+'건').join(' · ')||'기록 없음'}</p>}
    </details>)}</div>
  </div></details>;
}
