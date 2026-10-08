import { useSearchParams } from 'react-router-dom';
import { CURRENT_OBSERVATION_LABEL, CURRENT_OBSERVATION_MONTH,
  currentObservationPeriod, observationPeriod } from '../data/observationPeriod';

export default function ObservationPeriodNotice() {
  const [search, setSearch] = useSearchParams();
  const { from, to, isHistorical } = observationPeriod(search);
  const isCurrent = !isHistorical && from === CURRENT_OBSERVATION_MONTH && to === CURRENT_OBSERVATION_MONTH;
  return <div className="mt-3 rounded-lg bg-blue-50 p-3 text-xs text-slate-600" aria-label="관측 조회 기준월">
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <strong className="text-blue-800">현황 기준 {CURRENT_OBSERVATION_LABEL}</strong>
      <span>{isHistorical ? '명시적 역사 조회' : '선택 관측기간'}: {from} ~ {to}</span>
      {!isCurrent && <button className="rounded border border-blue-200 bg-white px-2 py-1 text-blue-800 focus-visible:ring-2 focus-visible:ring-blue-500"
        onClick={() => setSearch(currentObservationPeriod(search))}>현황 기준월 보기</button>}
    </div>
    <p className="mt-2">과거 자료는 원천과 시작월·종료월을 선택하세요. 선택 기간의 자료 보유 수는 현재 운영 시설 수와 다릅니다. 서비스·모델·문서 등록부는 각 화면의 별도 조회 범위를 확인하세요.</p>
  </div>;
}
