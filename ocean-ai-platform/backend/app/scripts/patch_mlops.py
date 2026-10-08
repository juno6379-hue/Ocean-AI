# 파일 역할: 기존 모델 운영 코드 수정을 위한 보조 스크립트입니다.
import os

file_path = r"C:\AI_Observation\ocean-ai-platform\frontend\src\pages\MLOps.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    "import React, { useState } from 'react';",
    "import React, { useState, useEffect } from 'react';\nimport axios from 'axios';"
)

# 2. Replace the static variables with state and useEffect
static_data_block = """  // Mock Data
  const statusData = [
    { name: '운영중', value: 8, percent: '33.3%', color: '#10B981' },
    { name: '검증중', value: 3, percent: '12.5%', color: '#3B82F6' },
    { name: '승인대기', value: 5, percent: '20.8%', color: '#F59E0B' },
    { name: '재학습 필요', value: 4, percent: '16.7%', color: '#EF4444' },
    { name: '보류', value: 4, percent: '16.7%', color: '#94A3B8' },
  ];

  const causeData = [
    { name: '데이터 드리프트', value: 12, percent: '33.3%', color: '#6366F1' },
    { name: '라벨 부족', value: 7, percent: '19.4%', color: '#3B82F6' },
    { name: '센서 교체 영향', value: 6, percent: '16.7%', color: '#3B82F6' },
    { name: '결측 증가', value: 6, percent: '16.7%', color: '#3B82F6' },
    { name: '임계값 부적합', value: 5, percent: '13.9%', color: '#3B82F6' },
  ];

  const modelList = [
    { name: '조위 AI 품질처리 모델', version: 'v2.3', target: '조위', range: '전체', status: '운영중', statusColor: 'text-emerald-600', date: '05/27', perf: 'F1 0.93 / RMSE 4.1', deploy: '배포완료', deployColor: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
    { name: '후포 조위 특화 모델', version: 'v1.8', target: '조위', range: '후포(LASER)', status: '검증중', statusColor: 'text-blue-600', date: '05/26', perf: 'F1 0.91 / RMSE 4.8', deploy: '승인대기', deployColor: 'text-amber-600 bg-amber-50 border-amber-200' },
    { name: '제주 조위 특화 모델', version: 'v1.5', target: '조위', range: '제주(LASER)', status: '운영중', statusColor: 'text-emerald-600', date: '05/20', perf: 'F1 0.92 / RMSE 4.3', deploy: '배포완료', deployColor: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
    { name: '파고 이상탐지 모델', version: 'v0.9', target: '파고', range: '동해안', status: '재학습 필요', statusColor: 'text-red-600', date: '05/18', perf: 'F1 0.84 / RMSE 6.7', deploy: '보류', deployColor: 'text-slate-600 bg-slate-100 border-slate-200' },
    { name: 'HF-Radar 유속장 모델', version: 'v1.1', target: '유속', range: '남해권', status: '운영중', statusColor: 'text-emerald-600', date: '05/22', perf: 'F1 0.89 / RMSE 5.1', deploy: '배포완료', deployColor: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  ];

  const retrainHistory = [
    { id: 'TR-20250527-001', model: '조위 AI 품질처리 모델', range: '05/01 - 05/27', perf: '0.91 → 0.93 / 4.6 → 4.1', status: '승인완료', statusColor: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
    { id: 'TR-20250522-003', model: 'HF-Radar 유속장 모델', range: '04/21 - 05/22', perf: '0.87 → 0.89 / 5.4 → 5.1', status: '승인완료', statusColor: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
    { id: 'TR-20250518-002', model: '파고 이상탐지 모델', range: '04/11 - 05/18', perf: '0.80 → 0.84 / 7.1 → 6.7', status: '승인대기', statusColor: 'text-amber-600 bg-amber-50 border-amber-200' },
    { id: 'TR-20250513-001', model: '제주 조위 특화 모델', range: '04/16 - 05/13', perf: '0.90 → 0.92 / 4.7 → 4.3', status: '승인완료', statusColor: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
    { id: 'TR-20250508-002', model: '후포 조위 특화 모델', range: '04/08 - 05/08', perf: '0.88 → 0.91 / 5.2 → 4.8', status: '승인대기', statusColor: 'text-amber-600 bg-amber-50 border-amber-200' },
  ];"""

new_state_logic = """  const [modelList, setModelList] = useState<any[]>([]);
  const [retrainHistory, setRetrainHistory] = useState<any[]>([]);
  const [totalModels, setTotalModels] = useState(24);
  const [statusData, setStatusData] = useState<any[]>([
    { name: '운영중', value: 8, percent: '33.3%', color: '#10B981' },
    { name: '검증중', value: 3, percent: '12.5%', color: '#3B82F6' },
    { name: '승인대기', value: 5, percent: '20.8%', color: '#F59E0B' },
    { name: '재학습 필요', value: 4, percent: '16.7%', color: '#EF4444' },
    { name: '보류', value: 4, percent: '16.7%', color: '#94A3B8' },
  ]);

  const fetchData = async () => {
    try {
      const sumRes = await axios.get('http://localhost:8080/api/mlops/summary');
      const histRes = await axios.get('http://localhost:8080/api/mlops/retrain-history');
      
      const st = sumRes.data.counts;
      const total = sumRes.data.total || 1; 
      setTotalModels(sumRes.data.total);
      
      setStatusData([
        { name: '운영중', value: st.ACTIVE, percent: `${Math.round(st.ACTIVE/total*100)}%`, color: '#10B981' },
        { name: '검증중', value: st.VALIDATING, percent: `${Math.round(st.VALIDATING/total*100)}%`, color: '#3B82F6' },
        { name: '재학습중', value: st.RETRAINING || 0, percent: `${Math.round((st.RETRAINING || 0)/total*100)}%`, color: '#8B5CF6' },
        { name: '재학습 필요', value: st.RETRAIN_REQUIRED, percent: `${Math.round(st.RETRAIN_REQUIRED/total*100)}%`, color: '#EF4444' },
      ]);

      const mappedModels = sumRes.data.models.map((m: any) => ({
        id: m.model_id,
        name: m.name,
        version: m.version,
        target: m.target,
        range: '전체',
        status: m.status === 'ACTIVE' ? '운영중' : m.status === 'VALIDATING' ? '검증중' : m.status === 'RETRAINING' ? '재학습중' : m.status === 'RETRAIN_REQUIRED' ? '재학습 필요' : m.status,
        statusColor: m.status === 'ACTIVE' ? 'text-emerald-600' : m.status === 'VALIDATING' ? 'text-blue-600' : m.status === 'RETRAINING' ? 'text-purple-600' : 'text-red-600',
        date: m.deployed_at,
        perf: m.metrics ? `F1 ${JSON.parse(m.metrics).F1} / RMSE ${JSON.parse(m.metrics).RMSE}` : '',
        deploy: m.status === 'ACTIVE' ? '배포완료' : '대기',
        deployColor: m.status === 'ACTIVE' ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : 'text-amber-600 bg-amber-50 border-amber-200'
      }));
      setModelList(mappedModels);

      const mappedHist = histRes.data.history.map((h: any) => ({
        id: h.training_id,
        model: h.model_name,
        range: '전체',
        perf: h.performance_before && h.performance_after ? `${JSON.parse(h.performance_before).F1} → ${JSON.parse(h.performance_after).F1}` : '-',
        status: h.status === 'COMPLETED' ? '승인완료' : h.status,
        statusColor: h.status === 'COMPLETED' ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : 'text-amber-600 bg-amber-50 border-amber-200'
      }));
      setRetrainHistory(mappedHist);
      
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleRetrain = async (modelId: string) => {
    alert("모델 재학습을 시작합니다! (백그라운드 진행)");
    try {
      await axios.post('http://localhost:8080/api/mlops/retrain', { model_id: modelId });
      fetchData();
    } catch(e) {
      console.error(e);
    }
  };

  const causeData = [
    { name: '데이터 드리프트', value: 12, percent: '33.3%', color: '#6366F1' },
    { name: '라벨 부족', value: 7, percent: '19.4%', color: '#3B82F6' },
    { name: '센서 교체 영향', value: 6, percent: '16.7%', color: '#3B82F6' },
    { name: '결측 증가', value: 6, percent: '16.7%', color: '#3B82F6' },
    { name: '임계값 부적합', value: 5, percent: '13.9%', color: '#3B82F6' },
  ];"""

content = content.replace(static_data_block, new_state_logic)

# 3. Add onClick to play button inside modelList.map
content = content.replace(
    """<button className="hover:text-blue-600"><Play className="w-3.5 h-3.5" /></button>""",
    """<button className="hover:text-blue-600" onClick={() => handleRetrain(row.id)} title="재학습 시작"><Play className="w-3.5 h-3.5" /></button>"""
)

# 4. Replace hardcoded "24" models with `{totalModels}`
content = content.replace(
    """{ title: '전체 모델 수', val: '24',""",
    """{ title: '전체 모델 수', val: totalModels.toString(),"""
)
content = content.replace(
    """<p className="text-sm font-black text-slate-800">24개</p>""",
    """<p className="text-sm font-black text-slate-800">{totalModels}개</p>"""
)
content = content.replace(
    """<span className="text-slate-500">전체 24건</span>""",
    """<span className="text-slate-500">전체 {totalModels}건</span>"""
)
content = content.replace(
    """<span className="text-slate-500">전체 12건</span>""",
    """<span className="text-slate-500">전체 {retrainHistory.length}건</span>"""
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("MLOps.tsx UI patched successfully.")
