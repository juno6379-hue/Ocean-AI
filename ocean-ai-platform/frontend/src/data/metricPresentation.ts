/** Missing inputs and an empty evaluation population must not become numeric zero. */
export const finiteMetric = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
export const countMetric = (value: unknown) => finiteMetric(value) && value >= 0 ? value.toLocaleString('ko-KR') : '필요입력 없음';
export function percentMetric(value: unknown, population: unknown) {
  if (finiteMetric(population) && population === 0) return '평가대상 없음';
  if (!finiteMetric(population) || population < 0 || !finiteMetric(value) || value < 0 || value > 100) return '필요입력 없음';
  return `${value.toLocaleString('ko-KR', {minimumFractionDigits: 1, maximumFractionDigits: 2})}%`;
}
export const literalMetric = (value: unknown) => value === null ? 'NULL' : value === '' ? '빈 문자열' : JSON.stringify(value);
export const isNumericMetricState = (state: unknown) => ['AVAILABLE', 'EMPTY_SCOPE', 'PARTIAL_CATALOG_COUNTS'].includes(String(state));

export type GridMetric = {status:string;holding_fraction_percent:number|null;held_slots:number|null;
  expected_slots:number|null;eligible_channel_months:number;excluded_channel_months:number;reason:string};
export type MetricCompletion = {state:string;reason?:string;snapshot:string|null;source:string;from_month:string;to_month:string;
  calculation_coverage?:{selected_held_months:number;fully_scanned_held_months:number;grid_applies_to_full_selected_scope:boolean};
  raw:{held_rows:number;missing_value_rate:number|null;numeric_row_rate:number|null;invalid_time_rate:number|null;
    source_qc_presence_rate:number|null;source_qc_primary_fields:string[];duplicate_timestamp_rows:number|null;receipt_diagnostics?:unknown;
    qc_codes:{field:string;literal:string|null;count:number;percent_of_field_rows:number|null}[];grid:GridMetric;
    stations:{station_code:string;held_rows:number;missing_value_rate:number|null;source_qc_presence_rate:number|null;grid:GridMetric;receipt_diagnostics?:unknown}[]}|null;
  report_reference:{status:string;normal_rates:{station_code:string;station_name:string;item_label:string;value:number|null;
    literal:string;status:string;pdf_page:number;table_id:string}[];unweighted_reference_mean_percent:number|null;
    numeric_reference_values:number;excluded_reference_values:number;reason:string}|null;
  blocked_metrics:{key:string;label:string;status:string;reason:string;required_inputs:string[]}[];limitations:string[]};
export function gridPercent(grid: GridMetric | undefined) {
  return percentMetric(grid?.holding_fraction_percent, grid?.expected_slots);
}
export function gridCoverageLabel(data: MetricCompletion | null) {
  const scope=data?.calculation_coverage;
  if (!scope || !Number.isSafeInteger(scope.selected_held_months) || !Number.isSafeInteger(scope.fully_scanned_held_months)
      || scope.selected_held_months < 1 || scope.fully_scanned_held_months < 0 || scope.fully_scanned_held_months > scope.selected_held_months) return '';
  return `원천 재검사 ${scope.fully_scanned_held_months}/${scope.selected_held_months}개월${scope.grid_applies_to_full_selected_scope?'':' · 완료한 범위의 격자율'}`;
}
export function qcPresencePercent(raw: MetricCompletion['raw'] | undefined) {
  if (raw && raw.held_rows > 0 && raw.source_qc_primary_fields.length === 0) return 'QC 필드 없음';
  return percentMetric(raw?.source_qc_presence_rate, raw?.held_rows);
}

export function validMetricCompletion(value: unknown, query: URLSearchParams) {
  if (!value || typeof value!=='object') return false;
  const response=value as Record<string,any>;
  if (!['AVAILABLE','EMPTY_SCOPE','PARTIAL_CATALOG_COUNTS','UNAVAILABLE_PERIOD','STALE','UNAVAILABLE'].includes(response.state)) return false;
  for (const key of ['source','from_month','to_month']) {
    if (response[key]!=null && response[key]!==query.get(key)) return false;
  }
  if (!isNumericMetricState(response.state)) return true;
  return Boolean(response.snapshot && response.source===query.get('source') && response.from_month===query.get('from_month') && response.to_month===query.get('to_month')
    && response.scope?.station===(query.get('station')||'') && response.scope?.item===(query.get('item')||'')
    && response.raw && finiteMetric(response.raw.held_rows) && response.raw.grid
    && Array.isArray(response.raw.stations) && Array.isArray(response.raw.qc_codes) && Array.isArray(response.raw.source_qc_primary_fields)
    && response.report_reference && Array.isArray(response.report_reference.normal_rates));
}
