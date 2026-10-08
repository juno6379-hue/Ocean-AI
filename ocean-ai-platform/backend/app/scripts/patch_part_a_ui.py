# 파일 역할: 기존 업무지원 화면 구성을 위한 보조 스크립트입니다.
import os

def patch_file(file_path, old_text, new_text):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if old_text in content:
        content = content.replace(old_text, new_text)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {os.path.basename(file_path)}")
    else:
        print(f"Could not find target block in {os.path.basename(file_path)}")

# 1. Dashboard.tsx
dash_path = r"C:\AI_Observation\ocean-ai-platform\frontend\src\pages\Dashboard.tsx"
dash_old_import = "import React, { useState, useEffect } from 'react';"
dash_new_import = "import React, { useState, useEffect } from 'react';\nimport axios from 'axios';"

dash_old_state = """  // Mock Model Data (추후 DB 연동)
  const perfTrendData = [
    { version: 'v2.0', f1: 0.86, rmse: 5.3 },
    { version: 'v2.1', f1: 0.89, rmse: 4.8 },
    { version: 'v2.2', f1: 0.91, rmse: 4.6 },
    { version: 'v2.3', f1: 0.93, rmse: 4.1 },
  ];

  const mlopsAlerts = [
    { icon: <AlertCircle className="w-4 h-4 text-red-500" />, text: '데이터 드리프트 감지', sub: '파고 이상탐지 모델', time: '10:25' },
    { icon: <AlertTriangle className="w-4 h-4 text-amber-500" />, text: '모델 성능 저하 감지', sub: '조위 특화 모델', time: '10:18' },
    { icon: <CheckCircle className="w-4 h-4 text-emerald-500" />, text: '재학습 완료', sub: '유속장 예측 모델', time: '10:05' },
  ];

  const recentReports = [
    { title: '주간 조위 이상치 분석 리포트', date: '2025-05-28', author: '시스템', status: '발행완료', statusColor: 'text-emerald-600 bg-emerald-50' },
    { title: '동해안 파고 급증 패턴 보고', date: '2025-05-27', author: '김연구원', status: '승인대기', statusColor: 'text-amber-600 bg-amber-50' },
    { title: '수온 센서 교체 주기 분석', date: '2025-05-26', author: '시스템', status: '발행완료', statusColor: 'text-emerald-600 bg-emerald-50' },
  ];"""

dash_new_state = """  // DB Fetched Data
  const [perfTrendData, setPerfTrendData] = useState<any[]>([]);
  const [mlopsAlerts, setMlopsAlerts] = useState<any[]>([]);
  const [recentReports, setRecentReports] = useState<any[]>([]);

  useEffect(() => {
    const fetchPartA = async () => {
      try {
        const perfRes = await axios.get('http://localhost:8080/api/dashboard/performance');
        setPerfTrendData(perfRes.data.perfTrendData || []);
        
        const alertRes = await axios.get('http://localhost:8080/api/qc/alerts');
        const mappedAlerts = alertRes.data.alerts.map((a: any) => ({
          icon: a.status === 'ANOMALY' ? <AlertCircle className="w-4 h-4 text-red-500" /> : <AlertTriangle className="w-4 h-4 text-amber-500" />,
          text: a.text,
          sub: a.sub,
          time: a.time
        }));
        setMlopsAlerts(mappedAlerts);

        const repRes = await axios.get('http://localhost:8080/api/reports/list');
        const mappedReports = repRes.data.reports.slice(0,3).map((r: any) => ({
          title: r.title,
          date: r.date,
          author: r.author,
          status: r.status,
          statusColor: r.statusColor
        }));
        setRecentReports(mappedReports);
      } catch (e) { console.error(e); }
    };
    fetchPartA();
    const interval = setInterval(fetchPartA, 5000);
    return () => clearInterval(interval);
  }, []);"""

patch_file(dash_path, dash_old_import, dash_new_import)
patch_file(dash_path, dash_old_state, dash_new_state)


# 2. QCCopilot.tsx
qc_path = r"C:\AI_Observation\ocean-ai-platform\frontend\src\pages\QCCopilot.tsx"
qc_old_import = "import React, { useState, useRef, useEffect } from 'react';"
qc_new_import = "import React, { useState, useRef, useEffect } from 'react';\nimport axios from 'axios';"

qc_old_state = """  // Mock Data
  const recentAlerts = [
    { id: 1, type: '이상탐지', station: 'ST-001 (인천)', time: '10:25 KST', desc: '조위 데이터 스파이크 감지 (30cm 초과)', severity: 'high' },
    { id: 2, type: '결측경고', station: 'ST-045 (후포)', time: '09:12 KST', desc: '1시간 이상 데이터 미수신', severity: 'medium' },
    { id: 3, type: '센서이상', station: 'ST-022 (제주)', time: '08:45 KST', desc: '수온 데이터 드리프트 의심', severity: 'low' },
  ];"""

qc_new_state = """  // Fetched Data
  const [recentAlerts, setRecentAlerts] = useState<any[]>([]);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await axios.get('http://localhost:8080/api/qc/alerts');
        const mapped = res.data.alerts.map((a: any, i: number) => ({
          id: a.id,
          type: a.status === 'ANOMALY' ? '이상탐지' : '결측/경고',
          station: '관측소 자동감지',
          time: a.time,
          desc: a.sub,
          severity: a.status === 'ANOMALY' ? 'high' : 'medium'
        }));
        setRecentAlerts(mapped);
      } catch (e) { console.error(e); }
    };
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, []);"""

patch_file(qc_path, qc_old_import, qc_new_import)
patch_file(qc_path, qc_old_state, qc_new_state)


# 3. Reports.tsx
rep_path = r"C:\AI_Observation\ocean-ai-platform\frontend\src\pages\Reports.tsx"
rep_old_import = "import React, { useState, useRef, useEffect } from 'react';"
rep_new_import = "import React, { useState, useRef, useEffect } from 'react';\nimport axios from 'axios';"

rep_old_state = """  // Mock Data
  const reportList = [
    { id: 'REP-20250528-01', title: '5월 4주차 전국 조위 관측망 이상치 종합 분석', date: '2025-05-28', author: '시스템 자동생성', type: '주간 리포트', status: '초안 (승인대기)', statusColor: 'text-amber-600 bg-amber-50' },
    { id: 'REP-20250527-02', title: '동해안 후포 관측소 센서 드리프트 의심 건', date: '2025-05-27', author: '김민수 연구원', type: '이상 징후 분석', status: '발행완료', statusColor: 'text-emerald-600 bg-emerald-50' },
    { id: 'REP-20250525-01', title: '남해권 HF-Radar 유속장 예측결과 비교', date: '2025-05-25', author: '시스템 자동생성', type: '정기 리포트', status: '발행완료', statusColor: 'text-emerald-600 bg-emerald-50' },
    { id: 'REP-20250521-01', title: '5월 3주차 전국 조위 관측망 이상치 종합 분석', date: '2025-05-21', author: '시스템 자동생성', type: '주간 리포트', status: '발행완료', statusColor: 'text-emerald-600 bg-emerald-50' },
  ];"""

rep_new_state = """  // Fetched Data
  const [reportList, setReportList] = useState<any[]>([]);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const res = await axios.get('http://localhost:8080/api/reports/list');
        const mapped = res.data.reports.map((r: any) => ({
          id: r.id,
          title: r.title,
          date: r.date,
          author: r.author,
          type: r.type,
          status: r.status,
          statusColor: r.statusColor
        }));
        setReportList(mapped);
      } catch(e) { console.error(e); }
    };
    fetchReports();
    const interval = setInterval(fetchReports, 5000);
    return () => clearInterval(interval);
  }, []);"""

patch_file(rep_path, rep_old_import, rep_new_import)
patch_file(rep_path, rep_old_state, rep_new_state)

print("Part A UI patches complete.")
