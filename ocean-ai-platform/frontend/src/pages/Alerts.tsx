// 파일 역할: 이상 알림과 사건 상태를 표시합니다.
import { API_BASE_URL } from '../api/client';
import React, { useState, useEffect } from 'react';
import { apiClient as axios } from '../api/client';
import { AlertTriangle, Check, X, ClipboardCheck, Clock } from 'lucide-react';

interface ApprovalTask {
  id: string;
  task_type: string;
  reference_id: string;
  content_payload: string;
  status: string;
  created_at: string;
}

const Alerts: React.FC = () => {
  const [approvals, setApprovals] = useState<ApprovalTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchApprovals();
  }, []);

  const fetchApprovals = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/approvals/pending`);
      setApprovals(res.data.approvals.map((a: any) => ({
        id: `${a.target_type}:${a.target_id}`, task_type: a.target_type, reference_id: a.target_id,
        content_payload: JSON.stringify(a.data), status: a.status, created_at: ''
      })));
      setError('');
    } catch (err) {
      console.error(err);
      setError('승인 대기 목록을 조회하지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const parseContent = (payload: string) => {
    try {
      return JSON.parse(payload);
    } catch {
      return {};
    }
  };

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    const task = approvals.find(a => a.id === id);
    if (!task) return;
    try {
      await axios.post(`${API_BASE_URL}/approvals/${action}`, { target_type: task.task_type, target_id: task.reference_id, comment: '웹 검토 화면에서 처리' });
      await fetchApprovals();
    } catch { setError('처리되지 않았습니다. 검토자 인증과 대상 상태를 확인하세요.'); }
  };

  return (
    <div className="p-6 bg-[#F8FAFC] min-h-full">
      <div className="flex items-center gap-3 mb-6">
        <ClipboardCheck className="w-8 h-8 text-amber-600" />
        <h2 className="text-2xl font-bold text-slate-800">검토·승인 대기함</h2>
      </div>

      {error && <p role="alert" className="text-red-700 mb-4">{error}</p>}
      {loading ? (
        <div className="flex justify-center py-10"><Clock className="w-6 h-6 animate-spin text-slate-400" /></div>
      ) : error ? null : approvals.length === 0 ? (
        <div className="bg-white p-10 rounded-2xl shadow-sm border border-slate-100 flex flex-col items-center">
          <AlertTriangle className="w-12 h-12 text-slate-300 mb-4" />
          <h3 className="text-lg font-medium text-slate-600">현재 대기 중인 결재 건이 없습니다.</h3>
          <p className="text-slate-400 mt-2">QC 변경·라벨·보고서·모델의 검토 대기 건을 표시합니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {approvals.map(task => {
            const content = parseContent(task.content_payload);
            return (
              <div key={task.id} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow flex flex-col h-full">
                <div className="flex justify-between items-start mb-3">
                  <span className="bg-amber-100 text-amber-700 text-xs font-bold px-2 py-1 rounded">
                    {task.task_type}
                  </span>
                  <span className="text-xs text-slate-400">{task.created_at ? new Date(task.created_at).toLocaleString('ko-KR') : '요청 시각 미확인'}</span>
                </div>
                <h4 className="font-bold text-slate-800 mb-2 truncate" title={content.title || task.reference_id}>
                  {content.title || task.reference_id}
                </h4>
                
                <div className="bg-slate-50 p-3 rounded-lg text-sm text-slate-600 mb-4 flex-1">
                  <p className="mb-2"><span className="font-semibold text-slate-700">이슈 원인:</span> {content.error_cause || content.quality_label || '미기재'}</p>
                  <p><span className="font-semibold text-slate-700">권고 조치:</span> {content.qc_flag_final || '검토 필요'}</p>
                </div>

                <div className="flex gap-2 mt-auto pt-4 border-t border-slate-100">
                  <button onClick={() => handleAction(task.id, 'approve')} className="flex-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 py-2 rounded-lg font-medium flex items-center justify-center gap-1 transition-colors">
                    <Check className="w-4 h-4" /> 확정 승인
                  </button>
                  <button onClick={() => handleAction(task.id, 'reject')} className="flex-1 bg-rose-50 text-rose-600 hover:bg-rose-100 py-2 rounded-lg font-medium flex items-center justify-center gap-1 transition-colors">
                    <X className="w-4 h-4" /> 반려
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Alerts;
