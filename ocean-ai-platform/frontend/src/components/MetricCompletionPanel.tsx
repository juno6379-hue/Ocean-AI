import { useEffect, useState } from 'react';
import { API_BASE_URL, apiFetch } from '../api/client';
import { countMetric, gridPercent, literalMetric, percentMetric, qcPresencePercent, validMetricCompletion } from '../data/metricPresentation';
import type { MetricCompletion } from '../data/metricPresentation';

const missingInputLabels: Record<string, string> = {
  SAMPLING_CONTRACT: '승인된 관측 주기',
  SENSOR_EFFECTIVE_PERIOD: '물리 센서 운영 시행기간',
  TIMEZONE: '확정된 원천 시간대',
  EXPECTED_OBSERVATIONS: '기대 관측 수와 제외 정책',
  QC_CODEBOOK_EFFECTIVE_PERIOD: '원천 QC 코드 의미와 시행기간',
  APPROVED_QC_COUNTS: '승인된 QC 판정 수와 평가 분모',
  APPROVED_BAD_COUNTS: '승인된 BAD 판정 수와 평가 분모',
  RECEIPT_CLOCK_CONTRACT: '확정된 수신 시각 기준',
  EXPECTED_RECEIPT_GRID: '기대 수신 시간격자와 지연 허용 기준',
};

export function useMetricCompletion(query: string, revision: number, expectedSnapshot?: string, enabled=true) {
  const [received, setReceived] = useState<{query:string;data:MetricCompletion}|null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setReceived(null); setError(''); setLoading(true);
    if (!enabled) {setLoading(false);return () => controller.abort();}
    apiFetch(`${API_BASE_URL}/lake/metric-completion?${query}`, {signal:controller.signal})
      .then(async response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
      .then(value => {
        const scope = new URLSearchParams(query);
        const numericState=value?.state==='AVAILABLE'||value?.state==='EMPTY_SCOPE';
        if (!validMetricCompletion(value,scope)) throw new Error('참고 지표 응답의 범위·형식이 일치하지 않습니다.');
        if (!numericState) {value.raw=null;value.report_reference=null;}
        value.blocked_metrics=Array.isArray(value.blocked_metrics)?value.blocked_metrics:[];
        value.limitations=Array.isArray(value.limitations)?value.limitations:[];
        if (!controller.signal.aborted) setReceived({query,data:value});
      })
      .catch(reason => {if (!controller.signal.aborted) setError(`참고 지표 조회 실패: ${reason.message}`);})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [query, revision, enabled]);
  const sameScope = received?.query === query;
  const numericState=received?.data.state==='AVAILABLE'||received?.data.state==='EMPTY_SCOPE';
  const sameSnapshot = !numericState || !expectedSnapshot || received?.data.snapshot === expectedSnapshot;
  return {data:enabled && sameScope && sameSnapshot ? received?.data ?? null : null,loading,
    error:error || (sameScope && !sameSnapshot ? '검증본 전환 중 · 참고 지표와 관측 집계가 다릅니다. 새로고침하세요.' : '')};
}

export default function MetricCompletionPanel({data,loading,error}:{data:MetricCompletion|null;loading:boolean;error:string}) {
  const raw=data?.raw,reference=data?.report_reference;
  const waiting=loading?'조회 중':error?'조회 실패':data?.state==='UNAVAILABLE_PERIOD'?'해당 기간 진단 미등록':'필요입력 없음';
  return <section className="rounded-xl border border-blue-200 bg-white p-4 space-y-3" aria-label="원시 자료 참고 지표 및 산정 조건">
    <div className="flex flex-wrap justify-between gap-2"><h2 className="font-bold">원시 자료 참고 지표 · 운영 판정과 별도</h2><span className="text-xs text-blue-800">미승인 진단 / 보고서 인쇄값 참조</span></div>
    {data&&data.state!=='AVAILABLE'&&data.state!=='EMPTY_SCOPE'&&<p className="text-sm text-amber-800">{data.state==='STALE'?'검증본 갱신 필요':data.state==='UNAVAILABLE_PERIOD'?'해당 기간 진단 미등록':'필요입력 없음'} · {data.reason||'선택 범위의 현재 검증 자료가 없습니다.'}</p>}
    {loading&&<p role="status" className="text-sm">원시 격자·결측 표현·QC 코드 근거 조회 중…</p>}
    {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
    <div className="grid grid-cols-2 xl:grid-cols-6 gap-2 text-xs">{[
      ['시간격자 보유율 (참고)',raw?gridPercent(raw.grid):waiting,raw?.grid?.reason||'동일 채널·월의 원시 시간격자와 유일 보유 슬롯 필요'],
      ['원시 결측표현율',raw?percentMetric(raw.missing_value_rate,raw.held_rows):waiting,'원시 결측 표현 행 / 원천 보유 행 · 미수집 구간 결측률 아님'],
      ['수치 표현율',raw?percentMetric(raw.numeric_row_rate,raw.held_rows):waiting,'수치 해석 가능 행 / 원천 보유 행 · 사용 가능한 정상값 비율 아님'],
      ['원천 시각 해석불가율',raw?percentMetric(raw.invalid_time_rate,raw.held_rows):waiting,'원천 시각 해석불가 행 / 보유 행 · 시간대 확정과 별도'],
      ['원천 QC 표기율',raw?qcPresencePercent(raw):waiting,'기본 QC 필드에 코드 표기 행 / 보유 행 · 정상·BAD 또는 승인 비율 아님'],
      ['보고서 정상자료율 평균 (참조)',reference?percentMetric(reference.unweighted_reference_mean_percent,reference.numeric_reference_values):waiting,reference?.reason||'인쇄된 수치의 비가중 평균 · 원시자료 정상률 아님'],
    ].map(([label,value,note])=><article key={label} className="rounded-lg bg-slate-50 p-3"><h3 className="font-semibold">{label}</h3><p className="my-2 text-lg font-bold break-words">{value}</p><p className="text-slate-500">{note}</p></article>)}</div>
    {raw&&<p className="text-xs text-slate-600">격자 보유 {countMetric(raw.grid?.held_slots)} / 기대 슬롯 {countMetric(raw.grid?.expected_slots)} · 포함 채널/월 {countMetric(raw.grid?.eligible_channel_months)} / 제외 {countMetric(raw.grid?.excluded_channel_months)} · 중복 원천 시각 행 {countMetric(raw.duplicate_timestamp_rows)}. 시행기간·시계·물리 센서·중복 정책 승인 전 참고 값입니다.</p>}
    {raw&&<details className="text-xs"><summary className="cursor-pointer text-blue-800">원천 QC 코드 분포 · 원문 NULL·공백 보존 ({raw.qc_codes.length}종)</summary>
      <p className="mt-2">기본 QC 필드: {raw.source_qc_primary_fields?.join(', ')||'QC 필드 없음'} · 보조 FLAG는 별도 원문 분포이며 정상/BAD 의미를 해석하지 않습니다.</p>
      <div className="max-h-64 overflow-auto mt-2"><table className="w-full text-left"><thead><tr>{['원문 필드','원문 코드 표현','행 수','필드 보유 행 대비'].map(label=><th className="p-2" key={label}>{label}</th>)}</tr></thead><tbody>{raw.qc_codes.map((row,i)=><tr className="border-t" key={`${row.field}:${i}`}><td className="p-2">{row.field}</td><td><code className="whitespace-pre">{literalMetric(row.literal)}</code></td><td>{countMetric(row.count)}</td><td>{percentMetric(row.percent_of_field_rows,raw.held_rows)}</td></tr>)}</tbody></table></div>
      {!raw.qc_codes.length&&<p className="mt-2">{raw.held_rows===0?'평가대상 없음':'QC 필드 없음'} · 선택 원천에서 집계할 QC 코드 필드를 찾지 못했거나 평가대상 행이 없습니다. 정상 비율 0%로 해석하지 않습니다.</p>}
    </details>}
    {reference&&<details className="text-xs"><summary className="cursor-pointer text-blue-800">월간 보고서 정상자료율 인쇄값 · 수치 {reference.numeric_reference_values} / 제외 {reference.excluded_reference_values}</summary>
      <p className="my-2">{reference.reason} · {reference.status}. 가중치·분모·QC 시행 기준이 다른 자료와 평균·비율을 합산하지 않습니다.</p>
      <div className="max-h-64 overflow-auto"><table className="w-full text-left"><thead><tr>{['관측소/항목','원문 표현','수치','문서 위치'].map(label=><th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{reference.normal_rates.map((row,i)=><tr key={`${row.table_id}:${row.station_code}:${row.item_label}:${i}`} className="border-t"><td className="p-2">{row.station_name||row.station_code} · {row.item_label}</td><td>{row.literal} · {row.status}</td><td>{row.value==null?'필요입력 없음':percentMetric(row.value,1)}</td><td>PDF {row.pdf_page}쪽 · {row.table_id}</td></tr>)}</tbody></table></div>
    </details>}
    {data&&<details open className="text-xs"><summary className="cursor-pointer font-semibold text-amber-800">실제 운영 지표의 미확정 입력·평가 대상</summary><div className="grid md:grid-cols-2 gap-2 mt-2">{data.blocked_metrics.map(metric=><article key={metric.key} className="rounded-lg bg-amber-50 p-3"><h3 className="font-bold">{metric.label} · {metric.status==='INPUTS_MISSING'?'산정 근거 미확정':metric.status==='NO_TARGETS'?'평가대상 없음':metric.status}</h3><p className="mt-1">{metric.reason}</p><p className="text-slate-600 mt-1">필수 입력: {metric.required_inputs.map(input=>missingInputLabels[input]||input).join(' · ')}</p></article>)}</div></details>}
    {data&&<p className="text-[11px] text-slate-500">{data.source} · {data.from_month} ~ {data.to_month} · 검증본 {data.snapshot}<br/>{data.limitations.join(' · ')}</p>}
  </section>;
}
