import {observationContext} from './observationPeriod';

/** QC and AI menus default to an explicit sample. Existing observation queries stay live. */
export type WorkspaceDataMode = 'SAMPLE' | 'LIVE';

export const workspaceContextKeys = [
  'from', 'to', 'from_month', 'to_month', 'as_of_day', 'as_of_time',
  'date_from', 'date_to', 'station', 'station_id', 'item', 'variable_code',
  'network', 'sea', 'flag', 'qc_field', 'qc_literal', 'qc_literal_is_null',
  'preset', 'range', 'candidate', 'queue_offset', 'queue_limit',
] as const;

export function workspaceDataMode(search: URLSearchParams): WorkspaceDataMode {
  if (search.get('source') === 'SAMPLE') return 'SAMPLE';
  // Preserve explicit sources, including invalid values, so the existing view reports the error.
  if (search.get('data_mode') === 'LIVE' || search.get('source') || workspaceContextKeys.some(key => search.has(key))) return 'LIVE';
  return 'SAMPLE';
}

export function canonicalWorkspaceSearch(search: URLSearchParams): URLSearchParams {
  if (workspaceDataMode(search) === 'SAMPLE') return new URLSearchParams({source:'SAMPLE'});
  const next = new URLSearchParams(search);
  next.set('data_mode', 'LIVE');
  return next;
}

/** Explicit exits from sample mode cannot fall back to the default sample on reload. */
export function liveWorkspaceHref(path: '/qc' | '/ai-insights', source?: string): string {
  const search = new URLSearchParams({data_mode:'LIVE'});
  if (source) search.set('source', source);
  return path + '?' + search;
}

/** Sidebar and next-task links share the same mode boundary. */
export function workspaceMenuQuery(pathname: string, search: URLSearchParams, destination: string): string {
  const workspacePage = ['/qc','/copilot','/ai-insights'].includes(pathname);
  const sampleMode = pathname === '/qc/sample' || (workspacePage && workspaceDataMode(search) === 'SAMPLE');
  const context = sampleMode ? new URLSearchParams() : observationContext(search);
  // REGISTERED is a QC ledger, not an archive source for the other menus.
  if (context.get('source') === 'REGISTERED') context.delete('source');
  if (['/qc','/ai-insights'].includes(destination)) {
    if (sampleMode) return '?source=SAMPLE';
    if (workspacePage || search.get('data_mode') === 'LIVE') context.set('data_mode', 'LIVE');
  }
  return context.size ? '?' + context : '';
}
