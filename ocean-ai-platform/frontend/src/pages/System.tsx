// 파일 역할: 시스템 설정과 운영 상태를 표시합니다.
import { API_BASE_URL } from '../api/client';
import SourceConnections from '../components/SourceConnections';
import React, { useState, useEffect } from 'react';
import { apiClient as axios } from '../api/client';
import { isAxiosError } from 'axios';
import { Monitor, Play, CheckCircle, XCircle, Clock, Database, AlertTriangle } from 'lucide-react';

interface TestResult {
  test_id: string;
  workflow_name: string;
  test_scenario: string;
  test_status: string;
  expected_action: string;
  actual_action: string;
  execution_time_ms: number;
  created_at: string;
  error_message: string;
}

const System: React.FC = () => {
  const [results, setResults] = useState<TestResult[]>([]);
  const [running, setRunning] = useState(false);
  const [loadError,setLoadError] = useState('');
  const [loaded,setLoaded] = useState(false);
  const [demoMode, setDemoMode] = useState<boolean | null>(null);
  const [runtimeError, setRuntimeError] = useState('');
  const [runError, setRunError] = useState('');

  useEffect(() => {
    fetchResults();
    axios.get(`${API_BASE_URL}/runtime`)
      .then(res => setDemoMode(res.data.is_demo === true))
      .catch(() => setRuntimeError('실행 환경 조회 실패 · 자동 시험은 실행할 수 없습니다.'));
  }, []);

  const fetchResults = async () => {
    setLoaded(false); setResults([]); setLoadError('');
    try {
      const res = await axios.get(`${API_BASE_URL}/test-auto/results`);
      setResults(res.data.results); setLoaded(true); setLoadError('');
    } catch (err) {
      setLoadError('테스트 이력 조회 실패 · 실행 결과 미확인'); setLoaded(false);
    }
  };

  const runAllScenarios = async () => {
    if (demoMode !== true || running) return;
    setRunning(true);
    setRunError('');
    try {
      await axios.post(`${API_BASE_URL}/test-auto/run`, { test_type: "E2E" });
      await fetchResults();
    } catch (err) {
      const detail = isAxiosError(err) ? err.response?.data?.detail : null;
      setRunError(typeof detail === 'string' ? detail : '테스트 실행 실패 · 새 실행 결과가 확인되지 않았습니다.');
    } finally {
      setRunning(false);
    }
  };

  const successCount = results.filter(r => r.test_status === 'PASSED').length;
  const failCount = results.filter(r => r.test_status === 'FAILED').length;

  return (
    <div className="p-6 bg-[#F8FAFC] min-h-full">
      <SourceConnections />
      {loadError && <p role="alert" className="text-red-700">{loadError}</p>}
      {runtimeError && <p role="alert" className="text-red-700">{runtimeError}</p>}
      {runError && <p role="alert" className="text-red-700">{runError}</p>}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <Monitor className="w-8 h-8 shrink-0 text-blue-600" />
          <h2 className="text-2xl font-bold text-slate-800">테스트 자동화 관리</h2>
        </div>
        <button 
          onClick={runAllScenarios} 
          disabled={running || demoMode !== true}
          title={demoMode === true ? '데모 환경 합성 시험' : '실자료 환경에서는 합성 E2E 시험을 실행하지 않습니다.'}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 w-full sm:w-auto disabled:bg-blue-300"
        >
          {running ? <Clock className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {demoMode === true ? '데모 E2E 시나리오 실행' : demoMode === false ? '실자료 환경 · 자동 시험 사용 불가' : '실행 환경 확인 중'}
        </button>
      </div>
      <p className="mb-6 text-sm text-slate-600">자동 E2E 시나리오는 모의 자료와 예시 보고서를 사용하는 데모 전용 시험입니다. 실자료 환경에서는 기존 이력 조회만 제공하며, 실제 연결 검증은 위의 데이터 소스 연결 시험에서 확인합니다.</p>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex flex-col justify-center items-center">
          <span className="text-slate-500 text-sm font-medium">전체 테스트 수</span>
          <span className="text-3xl font-bold text-slate-800 mt-2">{loaded ? results.length : '—'}</span>
        </div>
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex flex-col justify-center items-center">
          <span className="text-slate-500 text-sm font-medium">성공 (PASSED)</span>
          <span className="text-3xl font-bold text-emerald-600 mt-2">{loaded ? successCount : '—'}</span>
        </div>
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex flex-col justify-center items-center">
          <span className="text-slate-500 text-sm font-medium">실패 (FAILED)</span>
          <span className="text-3xl font-bold text-red-600 mt-2">{loaded ? failCount : '—'}</span>
        </div>
        <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex flex-col justify-center items-center">
          <span className="text-slate-500 text-sm font-medium">성공률</span>
          <span className="text-3xl font-bold text-blue-600 mt-2">
            {loaded && results.length > 0 ? `${Math.round((successCount / results.length) * 100)}%` : '미산정'}
          </span>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="p-4 border-b border-slate-100 bg-slate-50">
          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-500" />
            테스트 실행 결과 (최근 50건)
          </h3>
        </div>
        <div className="p-0 overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100 text-slate-600 text-sm">
                <th className="p-4 font-semibold">시나리오 명</th>
                <th className="p-4 font-semibold text-center">상태</th>
                <th className="p-4 font-semibold">기대 결과</th>
                <th className="p-4 font-semibold">실제 결과</th>
                <th className="p-4 font-semibold text-center">실행시간</th>
                <th className="p-4 font-semibold">실행일시</th>
              </tr>
            </thead>
            <tbody>
              {results.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400">{loadError ? '테스트 이력을 조회하지 못했습니다.' : !loaded ? '테스트 이력을 조회하는 중…' : '등록된 테스트 이력이 없습니다.'}</td>
                </tr>
              ) : (
                results.map((res) => (
                  <tr key={res.test_id} className="border-b border-slate-50 hover:bg-slate-50/50">
                    <td className="p-4 font-medium text-slate-700">{res.test_scenario}</td>
                    <td className="p-4 text-center">
                      {res.test_status === 'PASSED' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700"><CheckCircle className="w-3 h-3" /> PASSED</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700"><XCircle className="w-3 h-3" /> FAILED</span>
                      )}
                    </td>
                    <td className="p-4 text-sm text-slate-600">{res.expected_action}</td>
                    <td className="p-4 text-sm text-slate-600">
                      {res.actual_action}
                      {res.error_message && (
                        <div className="mt-1 text-xs text-red-500 flex items-start gap-1">
                          <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          {res.error_message}
                        </div>
                      )}
                    </td>
                    <td className="p-4 text-center text-sm font-mono text-slate-500">{res.execution_time_ms}ms</td>
                    <td className="p-4 text-sm text-slate-500">{new Date(res.created_at).toLocaleString('ko-KR')}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default System;
