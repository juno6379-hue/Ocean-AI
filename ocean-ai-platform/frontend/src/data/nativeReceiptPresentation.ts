/** Native clock differences are measured values, never operational delay labels. */
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const count = (value: unknown): value is number => finite(value) && Number.isSafeInteger(value) && value >= 0;

export function nativeReceiptPresentation(value: unknown) {
  const pending = {value:'수신시각 집계 전',note:'',title:'선택 기간의 수신시각 집계가 없습니다.'};
  if (!value || typeof value !== 'object') return pending;
  const receipt = value as Record<string, any>;
  if (receipt.diagnostic_kind !== 'SOURCE_CLOCK_DIFFERENCE_NOT_OPERATIONAL_DELAY'
      || receipt.approved !== false || receipt.operational_delay !== false) return pending;
  if (receipt.state === 'FIELD_ABSENT' && receipt.receipt_field_state === 'FIELD_ABSENT') {
    return {value:'수신시각 필드 없음',note:'',title:'이 원천에는 수신시각 필드가 없습니다.'};
  }
  if (receipt.state === 'NO_COMPARABLE_PAIRS') {
    return {value:'비교 가능한 시각 없음',note:'',title:'원문 관측·수신시각을 함께 해석할 수 있는 행이 없습니다.'};
  }
  if (receipt.state === 'MIXED_CLOCK_REPRESENTATIONS') {
    return {value:'시계 표현 혼재',note:'',title:'offset 유무가 다른 시각을 임의로 같은 시간대로 환산하지 않습니다.'};
  }
  const delta = receipt.difference_seconds;
  if (receipt.state !== 'CALCULATED_NATIVE_CLOCK_DIFFERENCE' || receipt.receipt_field_state !== 'PRESENT'
      || !count(receipt.raw_rows) || !count(receipt.comparable_pair_rows) || receipt.comparable_pair_rows === 0
      || receipt.comparable_pair_rows > receipt.raw_rows || !delta
      || !['min','max','mean','p50','p95'].every(key => finite(delta[key]))
      || delta.min > delta.max || delta.mean < delta.min || delta.mean > delta.max
      || delta.p50 < delta.min || delta.p50 > delta.p95 || delta.p95 > delta.max) return pending;
  const number = (n: number) => n.toLocaleString('ko-KR',{maximumFractionDigits:2});
  return {value:`평균 ${number(delta.mean)}초`,note:`P95 ${number(delta.p95)}초`,
    title:`원문 수신−관측 시계차 · ${number(receipt.comparable_pair_rows)}행 · ${number(delta.min)}~${number(delta.max)}초. 운영 지연 판정과 별도입니다.`};
}
