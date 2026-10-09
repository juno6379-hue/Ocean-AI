/** Declared reporting basis, not a claim about the latest operating facilities. */
export const CURRENT_OBSERVATION_MONTH = '2026-07';
export const CURRENT_OBSERVATION_LABEL = '2026년 7월';
export const DEFAULT_OBSERVATION_SOURCE = 'GD_OBS_ST_MONTHLY';
export const HISTORICAL_OBSERVATION_SOURCE = 'HISTORICAL_RECONCILED';

type SearchValues = Pick<URLSearchParams, 'get'>;

/** Commit both dates together so partially edited inputs do not relabel results. */
export function applyObservationPeriod(search:URLSearchParams,from:string,to:string) {
  const month=/^[0-9]{4}-(0[1-9]|1[0-2])$/;
  if(!month.test(from)||!month.test(to)||from.startsWith('0000')||to.startsWith('0000')||from>to)return null;
  const next=new URLSearchParams(search);next.set('from',from);next.set('to',to);
  return next;
}

export function observationPeriod(search: SearchValues) {
  const source = search.get('source') || DEFAULT_OBSERVATION_SOURCE;
  const isHistorical = source === HISTORICAL_OBSERVATION_SOURCE;
  return {
    source,
    from: search.get('from') || (isHistorical ? '2011-01' : CURRENT_OBSERVATION_MONTH),
    to: search.get('to') || (isHistorical ? '2021-12' : CURRENT_OBSERVATION_MONTH),
    isHistorical,
  };
}

/** Keep only explicitly chosen context; each destination resolves its defaults. */
export function observationContext(search: SearchValues) {
  const context = new URLSearchParams();
  for (const key of ['source', 'from', 'to', 'network', 'sea', 'as_of_day', 'as_of_time']) {
    const value = search.get(key);
    if (value) context.set(key, value);
  }
  return context;
}

/** A source change must not silently replace the user's explicit period. */
export function selectObservationSource(search: URLSearchParams, source: string) {
  const next = new URLSearchParams(search);
  next.set('source', source);
  next.delete('station');
  next.delete('item');
  return next;
}

/** Explicit user action to return from a past/custom query to the reporting month. */
export function currentObservationPeriod(search: URLSearchParams) {
  const period = observationPeriod(search);
  const next = selectObservationSource(search, period.isHistorical ? DEFAULT_OBSERVATION_SOURCE : period.source);
  next.set('from', CURRENT_OBSERVATION_MONTH);
  next.set('to', CURRENT_OBSERVATION_MONTH);
  return next;
}
