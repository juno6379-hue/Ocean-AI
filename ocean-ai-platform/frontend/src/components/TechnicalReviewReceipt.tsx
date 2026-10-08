import { useEffect, useState } from 'react';
import { API_BASE_URL, apiClient } from '../api/client';

type Counts = Record<string, number>;
type Receipt = {
  status: string; approved: false; bundle_id: string; scope_label: string;
  semantic: {
    input_rows: number; exact_scope_keys: number; duplicate_scope_keys: number;
    dictionary_reference_counts: Counts; newly_exact_scoped_reference_rows: number;
    invalidated_cross_source_reference_rows: number; existing_period_conflict_rows: number;
    semantic_approvals: number; unit_application_approvals: number; timezone_approvals: number;
    qc_approvals: number; operational_rule_approvals: number;
    source_group_counts: Record<string, Counts>; checked_at: string; as_of: string;
  };
  semantic_receipt: { validation_errors: string[] };
  identity: {
    approved_identity_period_event_scopes?: number; eligible_members?: number;
    report_scope_extension?: {
      status: string; reviewed_report_rows: number; tide_current_rows: number; buoy_rows: number;
      hf_rows: number; science_rows: number; newly_added_report_rows?: number;
      exact_event_link_candidates?: number; unlinked_rows?: number; scope_description: string; approved: false;
    };
  };
};

const missingReasons: Record<string, string> = {
  SOURCE_SEMANTICS_NOT_APPROVED: '공통 의미 계약 미승인',
  SOURCE_UNIT_APPLICATION_UNRESOLVED: '원천 단위·배율·기준면 적용기간 미확정',
  PHYSICAL_SENSOR_PERIOD_UNRESOLVED: '실물 센서·수심/수층·설치/교체/철거 유효기간 미확정',
  SOURCE_TIMEZONE_UNRESOLVED: '원천 관측시각·수신시각 시간기준 미확정',
  SOURCE_QC_CODEBOOK_UNVERIFIED: '원천 QC 코드와 단계별 의미·공백 처리 계약 미확정',
  ADOPTED_RULE_VERSION_AND_EFFECTIVE_INTERVAL_UNVERIFIED: '채택 QC 규칙의 판본·시행기간 미확정',
  QC_APPROVAL_REQUIRED: '최종 QC 검토·승인 기록 필요',
};
const n = (value: number | undefined) => typeof value === 'number' ? value.toLocaleString() : '미확인';

export default function TechnicalReviewReceipt() {
  const [data, setData] = useState<Receipt | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true); setData(null); setError('');
    apiClient.get<Receipt>(`${API_BASE_URL}/data-lake/foundation/review-receipt`, { signal: controller.signal })
      .then(response => { if (active) setData(response.data); })
      .catch(() => { if (active) setError('검증된 기술검토 게시본을 읽지 못했습니다. 아래 집계와 승인 상태는 미조회입니다.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [attempt]);
  const counts = data?.semantic.dictionary_reference_counts;
  const events = data?.identity.report_scope_extension;
  return <section className="space-y-3 rounded-xl border bg-white p-5" aria-label="공통 의미·기간·사건 기술검토">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="font-bold text-lg">공통 의미·기간·사건 기술검토</h3>
      <button type="button" disabled={loading} onClick={() => setAttempt(value => value + 1)} className="rounded border px-3 py-1 text-sm disabled:opacity-50">{loading ? '조회 중…' : '검토 게시본 다시 조회'}</button>
    </div>
    {loading && <p role="status">기술검토의 범위·검증 원장·승인 상태를 조회 중입니다.</p>}
    {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-red-700">{error}</p>}
    {data && <>
      <p className="rounded border border-amber-200 bg-amber-50 p-3">{data.scope_label}</p>
      <p className="text-sm text-slate-600">검토 게시본 {data.bundle_id} · 시설 기준일 {data.semantic.as_of} · 기술검토 시각 {data.semantic.checked_at}</p>
      <p>등록된 채널-월 {n(data.semantic.input_rows)}그룹을 전수 정산했습니다. 정확 범위 키 {n(data.semantic.exact_scope_keys)}개 · 중복 {n(data.semantic.duplicate_scope_keys)}개. 원천별 보유행은 유일 관측 건수와 별도입니다.</p>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="border-b p-2">기술검토 항목</th><th className="border-b p-2">채널-월 그룹</th><th className="border-b p-2">판정 범위</th></tr></thead><tbody>
        <tr><td className="border-b p-2">정확 사전·시트 대조</td><td className="border-b p-2">{n(counts?.AUTO_VERIFIED_DICTIONARY_REFERENCE)}</td><td className="border-b p-2">사전 참조 확인 · 센서/단위/QC 승인과 별도</td></tr>
        <tr><td className="border-b p-2">새롭게 정확 사전 참조 확인</td><td className="border-b p-2">{n(data.semantic.newly_exact_scoped_reference_rows)}</td><td className="border-b p-2">원천 범위 혼합 수정</td></tr>
        <tr><td className="border-b p-2">이전 사전 참조 해소 판정 철회</td><td className="border-b p-2">{n(data.semantic.invalidated_cross_source_reference_rows)}</td><td className="border-b p-2">다른 원천·시트를 참조한 근거 부족</td></tr>
        <tr><td className="border-b p-2">원천 항목 코드 미등재</td><td className="border-b p-2">{n(counts?.EXACT_SOURCE_ITEM_NOT_IN_DICTIONARY)}</td><td className="border-b p-2">해당 원천 코드표 필요</td></tr>
        <tr><td className="border-b p-2">시트 범위 미확정</td><td className="border-b p-2">{n(counts?.WORKSHEET_SCOPE_UNRESOLVED)}</td><td className="border-b p-2">관측소 변천·시트 적용 근거 필요</td></tr>
        <tr><td className="border-b p-2">GR_OBS_ST 원천 대응 계약 미확정</td><td className="border-b p-2">{n(counts?.SOURCE_ADAPTER_UNVERIFIED)}</td><td className="border-b p-2">다른 원천의 코드표를 자동 적용하지 않음</td></tr>
        <tr><td className="border-b p-2">기존 기간 충돌</td><td className="border-b p-2">{n(data.semantic.existing_period_conflict_rows)}</td><td className="border-b p-2">재설치/철거/교체 사건 대조 필요</td></tr>
      </tbody></table></div>
      <p className="text-sm">원천별 그룹: {Object.entries(data.semantic.source_group_counts).map(([source, values]) => `${source} ${n(Object.values(values).reduce((total, value) => total + value, 0))}`).join(' · ')}. 기준 월별 원천은 전체의 일부입니다.</p>
      {events ? <div className="rounded border p-3 text-sm"><h4 className="font-semibold">보고서 표의 사건 누락 추가 검토</h4>
        <p>2025년 결과보고서 제2장, PDF 7–13페이지의 표 2-4~2-8을 검토했습니다.</p><p>검토한 보고서 표 {n(events.reviewed_report_rows)}행: 조위/해양관측소 {n(events.tide_current_rows)} · 부이 {n(events.buoy_rows)} · HF {n(events.hf_rows)} · 과학기지 {n(events.science_rows)}.</p>
        <p>추가 원문 사건행 {n(events.newly_added_report_rows)} · 관측 범위 연결 후보 {n(events.exact_event_link_candidates)} · 미연결 {n(events.unlinked_rows)}. 사건 후보 연결은 원인 확정·센서 대응·QC 승인과 별도입니다.</p>
        <details className="mt-2"><summary className="cursor-pointer">원문 검토 범위 기록</summary><p className="mt-1">{events.scope_description}</p></details>
      </div> : <p className="text-sm text-slate-600">보고서 표의 사건 누락 추가 검토 집계는 이 게시본에서 미조회입니다. 0건으로 판단하지 않습니다.</p>}
      <p className="rounded border border-amber-200 bg-amber-50 p-3 text-sm">이 게시본 기준 승인: 공통 의미 {n(data.semantic.semantic_approvals)} · 원천 단위 적용 {n(data.semantic.unit_application_approvals)} · 시간대 {n(data.semantic.timezone_approvals)} · 채택 QC 규칙 {n(data.semantic.operational_rule_approvals)} · 최종 QC {n(data.semantic.qc_approvals)}. 이 기술검토는 학습·운영 모델 등록을 실행하지 않습니다.</p>
      <details className="text-sm"><summary className="cursor-pointer font-semibold">미확정 이유와 다음 검토</summary><ul className="mt-2 list-disc space-y-1 pl-5">{data.semantic_receipt.validation_errors.map(reason => <li key={reason}>{missingReasons[reason] || reason}</li>)}</ul>
        <p className="mt-2">원문 검토는 게시 검증 기록에 명시한 문서·페이지·표 범위에 한정합니다. 다른 문서·전체기간 정밀검토로 확대하지 않습니다. 전체 원장 해시는 게시 시점에 검증자가 확인했고, 조회 시에는 작은 게시 검토 기록과 요약의 해시를 다시 확인합니다.</p>
      </details>
    </>}
  </section>;
}
