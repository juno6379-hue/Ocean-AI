// 파일 역할: 화면 경로와 공통 레이아웃을 구성합니다.
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import StationProfile from './pages/StationProfile';
import QCCopilot from './pages/QCCopilot';
import Observations from './pages/Observations';
import AIInsights from './pages/AIInsights';
import Equipment from './pages/Equipment';
import Reports from './pages/Reports';
import MLOps from './pages/MLOps';
import DataLake from './pages/DataLake';
import Forecasting from './pages/Forecasting';
import Alerts from './pages/Alerts';
import System from './pages/System';
import ServiceMonitoring from './pages/ServiceMonitoring';

/**
 * React Router�??�용???�체 ?�우???�정 ?�일?�니??
 * Layout??부모로 ?�고 ?��???�??�이지�??�더링합?�다.
 */
const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {/* 기본 경로???�?�보??*/}
        <Route index element={<Dashboard />} />
        
        {/* 관�??�황 ?�이지 */}
        <Route path="observations" element={<Observations />} />
        
        {/* 관측소 ?�로?�일 ?�이지 (URL ?�라미터�?관측소 ID ?�달) */}
        <Route path="profile/:id" element={<StationProfile />} />
        
        {/* QC Copilot 메인 ?�면 */}
        <Route path="qc" element={<QCCopilot />} />
        <Route path="copilot" element={<QCCopilot />} />
        
        {/* AI 분석 ?�사?�트 ?�면 */}
        <Route path="ai-insights" element={<AIInsights />} />

        {/* ?�비 & ?�영 관�??�면 */}
        <Route path="equipment" element={<Equipment />} />
        
        {/* 보고??& 문서 ?�면 */}
        <Route path="reports" element={<Reports />} />
        
        {/* MLOps 모델 관�??�면 */}
        <Route path="mlops" element={<MLOps />} />
        <Route path="data-lake" element={<DataLake />} />
        <Route path="forecasting" element={<Forecasting />} />
        
        {/* ?�비??모니?�링 ?�면 */}
        <Route path="service-monitoring" element={<ServiceMonitoring />} />
        
        {/* ?�림 �??�스???�면 */}
        <Route path="alerts" element={<Alerts />} />
        <Route path="system" element={<System />} />
        
        {/* ?�못??경로???�?�보?�로 리다?�렉??*/}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};

export default App;


