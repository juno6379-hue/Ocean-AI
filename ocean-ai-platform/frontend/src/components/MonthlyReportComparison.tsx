import { useEffect, useState } from 'react';
import { API_BASE_URL, apiFetch } from '../api/client';

/** Official publication counts remain separate from source-specific held records. */
export default function MonthlyReportComparison({source, from, to}: {source: string; from: string; to: string}) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const reportMonth = '2026-07';
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    const query = new URLSearchParams({month: reportMonth, source});
    apiFetch(`${API_BASE_URL}/lake/publication-comparison?${query}`, {signal: controller.signal})
      .then(async response => {if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json();})
      .then(value => {if (!controller.signal.aborted) setData(value);})
      .catch(reason => {if (!controller.signal.aborted) setError(`월간 보고서 대조 결과 조회 실패: ${reason.message}`);});
    return () => controller.abort();
  }, [source]);
  const inScope = from === reportMonth && to === reportMonth;
  const held = data?.selected_source_summary;
  const format = (value: unknown) => typeof value === 'number' ? value.toLocaleString('ko-KR') : '미확인';
  return <section className="rounded-xl border border-amber-200 bg-white p-4 space-y-3" aria-label="7월 월간해양정보 대조">
    <div className="flex flex-wrap justify-between gap-2"><h3 className="font-bold text-slate-800">2026년 7월 월간해양정보 · Parquet 대조</h3><span className="text-xs text-amber-800">기술 대조 · 운영 승인 전</span></div>
    {!inScope && <p className="text-xs text-amber-800">선택 기간은 {from} ~ {to}입니다. 아래 공식 현황은 2026년 7월 기준이며, 선택한 전체 기간과의 일치 판정이 아닙니다.</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {!data && !error && <p role="status" className="text-sm text-slate-500">월간 보고서 대조 기록 조회 중…</p>}
    {data && <>
      {data.audit_state !== 'CURRENT' && <p role="alert" className="text-sm text-red-700">{data.stale_note}</p>}
      <div className="grid gap-2 md:grid-cols-3 text-sm">
        <div className="rounded-lg bg-blue-50 p-3">공식 시설 현황<p className="font-bold">공개 {format(data.official_totals?.public_count)} · 공개 제한 {format(data.official_totals?.restricted_count)}개</p></div>
        <div className="rounded-lg bg-slate-50 p-3">선택 원천의 7월 보유 코드<p className="font-bold">{format(held?.station_count)}개 · {format(held?.held_rows)}행</p></div>
        <div className="rounded-lg bg-slate-50 p-3">선택 원천의 마지막 시각<p className="font-bold">{held?.last_clock || '조회 범위 없음'}</p></div>
      </div>
      <p className="text-xs text-slate-500">공식 시설 수는 보고서의 관측망 전체, 보유 코드는 선택 원천 전체 기준입니다. 관측망·해역 필터와 별도이며, 원천 사이의 같은 시설·중복 관측은 자동 합산하지 않습니다.</p>
      <div className="overflow-x-auto"><table className="w-full text-xs text-left"><thead className="bg-slate-50"><tr><th className="p-2">공식 시설 유형</th><th className="p-2">공개</th><th className="p-2">공개 제한</th></tr></thead><tbody>{(data.official_counts || []).map((row:any) => <tr key={row.category} className="border-t border-slate-100"><td className="p-2">{row.category}</td><td className="p-2">{format(row.public_count)}</td><td className="p-2">{format(row.restricted_count)}</td></tr>)}</tbody></table></div>
      <ul className="text-xs text-slate-700 space-y-1">{(data.findings || []).map((finding:any) => <li key={finding.code}>• {finding.message}</li>)}</ul>
      <p className="text-[11px] text-slate-500">{data.method_note} · 보고서 SHA256 {data.publication_sha256?.slice(0,16)}… · 대조 검증본 {data.snapshot}</p>
    </>}
  </section>;
}
