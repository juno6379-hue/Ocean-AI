/** Experimental release evidence is separate from the production registry. */
export type RawMetrics = { mae: number; rmse: number; pair_count: number };
export type ExperimentalModel = {
  model_id: string; variable_code: string; selected_model: string;
  artifact_sha256: string; source_membership_sha256: string; input_lags: number;
  split_counts: Record<string, number>;
  validation_metrics: Record<string, RawMetrics>; test_metrics: Record<string, RawMetrics>;
  last_values: number[]; last_native_times: string[];
};
export type ExperimentalRelease = {
  status: string; release_id: string; models: ExperimentalModel[];
  experimental: true; nonoperational: true; approved: false; production_eligible: false;
  unit: null; timezone: null; horizon_seconds: null; source_period: string; source_table: string; station_code: string;
};
const hash = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const record = (value: unknown): value is Record<string, any> => !!value && typeof value === 'object' && !Array.isArray(value);
const metrics = (value: unknown) => record(value) && Object.keys(value).length > 0 && Object.values(value).every(row =>
  record(row) && finite(row.mae) && row.mae >= 0 && finite(row.rmse) && row.rmse >= 0 &&
  Number.isInteger(row.pair_count) && row.pair_count > 0);
export function experimentalReleaseValid(value: unknown): value is ExperimentalRelease {
  if (!record(value) || value.status !== 'READY' || typeof value.release_id !== 'string' || !value.release_id ||
    value.experimental !== true || value.nonoperational !== true || value.approved !== false || value.production_eligible !== false ||
    value.unit !== null || value.timezone !== null || value.horizon_seconds !== null || value.source_period !== '2026-07' ||
    value.source_table !== 'GR_OBS_ST' || value.station_code !== 'DT_0001' || !Array.isArray(value.models) || value.models.length !== 3 ||
    !['AIR_PRES','WATER_TEMP','SALINITY'].every(id => value.models.some((row: unknown) => record(row) && row.model_id === id))) return false;
  return new Set(value.models.map(row => row?.model_id)).size === value.models.length && value.models.every(row => record(row) &&
    typeof row.model_id === 'string' && row.variable_code === row.model_id && ['PERSISTENCE','RIDGE'].includes(row.selected_model) &&
    hash(row.artifact_sha256) && hash(row.source_membership_sha256) && row.input_lags === 3 &&
    Array.isArray(row.last_values) && row.last_values.length === 3 && row.last_values.every(finite) &&
    Array.isArray(row.last_native_times) && row.last_native_times.length === 3 && row.last_native_times.every((v: unknown) => typeof v === 'string') &&
    record(row.split_counts) && ['TRAIN','VALIDATION','TEST'].every(split => Number.isInteger(row.split_counts[split]) && row.split_counts[split] > 0) &&
    metrics(row.validation_metrics) && metrics(row.test_metrics) && !!row.test_metrics[row.selected_model] && !!row.validation_metrics[row.selected_model]);
}
export function experimentalPredictionMatches(value: unknown, release: ExperimentalRelease, model: ExperimentalModel, values: number[]) {
  return record(value) && value.release_id === release.release_id && value.model_id === model.model_id &&
    value.artifact_sha256 === model.artifact_sha256 && finite(value.prediction) &&
    value.approved === false && value.production_eligible === false && value.unit === null && value.timezone === null && value.horizon_seconds === null &&
    value.prediction_target === 'NEXT_OBSERVED_NATIVE_ROW' && Array.isArray(value.input_values) &&
    value.input_values.length === 3 && value.input_values.every((v: unknown, i: number) => finite(v) && v === values[i]);
}
export function nativeValues(text: string): number[] | null {
  const parts = text.split(',').map(value => value.trim());
  if (parts.length !== 3 || parts.some(value => !value || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value))) return null;
  const values = parts.map(Number);
  return values.every(finite) ? values : null;
}
