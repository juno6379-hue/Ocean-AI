// 파일 역할: 대용량 관측자료 변환·통계·분석 단계 현황을 표시합니다.
import React, { useEffect, useState } from 'react';
import { getDataLakeSummary } from '../api';
import FoundationLake from '../components/FoundationLake';
const DataLake: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    getDataLakeSummary()
      .then(data => { if (active) setSummary(data); })
      .catch(() => { if (active) setError('기존 PostgreSQL 적재 통계 조회 실패 · 적재량 미확인'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const stages = ['원천 보존 및 체크섬','Parquet 파티션·품질 프로파일','결측 보간 및 QC Copilot','장기 추세 AI Insights','조위 Forecasting MLOps','승인·버전·재현성'];
  return <div className="p-8"><h1 className="text-3xl font-bold">Data Lake 자료 검증 및 활용</h1><p className="mt-3 text-slate-600">대용량 원천자료는 Data Lake에서 처리하고 운영 DB에는 요약 통계만 적재합니다.</p><div className="mt-6 bg-white border rounded-xl p-5"><h2 className="font-bold">기존 PostgreSQL 적재 통계</h2>{loading && <p role="status" className="text-sm text-slate-500 mt-2">기존 적재 통계 조회 중…</p>}{error && <p role="alert" className="text-sm text-red-700 mt-2">{error}</p>}{summary && <><p className="text-sm text-slate-600 mt-2">파티션 {summary.partitions}개 · 행 {summary.rows?.toLocaleString()}건 · 결측 {summary.missing?.toLocaleString()}건</p>{summary.partitions === 0 && <p className="text-sm text-slate-500 mt-2">이 통계 등록부에 적재 기록이 없습니다. 아래 파일 레이크의 보유량과는 별도입니다.</p>}</>}</div><FoundationLake /><div className="grid md:grid-cols-2 gap-4 mt-8">{stages.map(x => <div className="bg-white border rounded-xl p-5" key={x}><h2 className="font-bold">{x}</h2><p className="text-sm text-slate-500 mt-2">설계 및 실행 상태를 단계별로 관리합니다.</p></div>)}</div></div>;
};
export default DataLake;
