import { useEffect, useState } from 'react';
import { API_BASE_URL, apiClient } from '../api/client';

type Status = {
  enabled: boolean; mapping_version: string; auto_approved_contracts: number;
  registered_bindings: number; first_timestamp_utc: string | null; last_timestamp_utc: string | null;
  variables: {variable_code: string; rows: number}[];
};

export default function OperationalMappingStatus() {
  const [value, setValue] = useState<Status | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const control = new AbortController();
    const load = () => apiClient.get(`${API_BASE_URL}/source-contracts/auto-mapping/status`, {signal:control.signal})
      .then(response => {if (!control.signal.aborted) {setValue(response.data); setFailed(false);}})
      .catch(() => {if (!control.signal.aborted) {setValue(null); setFailed(true);}});
    void load();
    const timer = setInterval(() => void load(), 30000);
    return () => {control.abort(); clearInterval(timer);};
  }, []);
  return <section aria-label="운영 표준 매핑 적재 현황" className="bg-white border rounded-xl p-5 space-y-3">
    <h3 className="font-bold">운영 표준 매핑 · 자동 계약 및 Binding</h3>
    {failed ? <p role="alert" className="text-red-700">운영 적재 현황을 불러오지 못했습니다.</p> : value ? <>
      <div className="flex flex-wrap gap-6 text-sm">
        <p>시스템 승인 정책 <strong>{value.enabled ? '활성' : '비활성'}</strong></p>
        <p>자동 승인 계약 <strong>{value.auto_approved_contracts.toLocaleString()}건</strong></p>
        <p>등록 Binding <strong>{value.registered_bindings.toLocaleString()}행</strong></p>
        <p>매핑 판본 <strong>{value.mapping_version}</strong></p>
      </div>
      <p className="text-xs text-slate-600">운영 테이블 관측기간 (UTC): {value.first_timestamp_utc ?? '적재 없음'} ~ {value.last_timestamp_utc ?? '적재 없음'}</p>
      {value.variables.length > 0 && <div className="flex flex-wrap gap-2">{value.variables.map(row =>
        <span key={row.variable_code} className="rounded bg-blue-50 px-3 py-1 text-sm text-blue-800">{row.variable_code} · {row.rows.toLocaleString()}행</span>)}</div>}
      <p className="text-xs text-slate-600">파일·원문을 확인한 시스템 정책으로 운영용 변수·단위·시각을 표준화합니다. 실제 센서 확인, 최종 QC 판정, 학습·모델 승인 상태는 별도입니다. 적재 범위는 위 관측기간이며 전체 과거 자료 적재 완료를 뜻하지 않습니다.</p>
    </> : <p className="text-sm text-slate-500">운영 적재 현황 조회 중…</p>}
  </section>;
}
