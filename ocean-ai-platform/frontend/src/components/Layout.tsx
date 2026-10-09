// 파일 역할: 업무 메뉴와 화면 공통 배치를 제공합니다.
import React, { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import {
  Waves, LayoutDashboard, Activity, CheckCircle,
  Lightbulb, Settings, FileText, Cpu, AlertTriangle, Monitor,
  MenuSquare, Menu, X, Database
} from 'lucide-react';
import Chatbot from './Chatbot';
import OperatorSession from './OperatorSession';
import WorkflowStatus from './WorkflowStatus';
import MenuPurpose from './MenuPurpose';
import { menuPurposeFor } from '../data/menuPurposes';
import { observationContext } from '../data/observationPeriod';

const Layout: React.FC = () => {
  const location = useLocation();
  const path = location.pathname;
  const compactWorkspace=path==='/observations'||path==='/qc'||path==='/copilot';
  const context = observationContext(new URLSearchParams(location.search));
  const contextQuery=context.size ? `?${context}` : '';
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const navItems = [
    { name: '종합 대시보드', path: '/', icon: LayoutDashboard },
    { name: '관측 현황', path: '/observations', icon: Activity },
    { name: '품질 현황 (QC)', path: '/qc', icon: CheckCircle },
    { name: 'AI 분석 인사이트', path: '/ai-insights', icon: Lightbulb },
    { name: '장비 & 운영 관리', path: '/equipment', icon: Settings },
    { name: '서비스 모니터링', path: '/service-monitoring', icon: Activity },
    { name: '보고서 & 문서', path: '/reports', icon: FileText },
    { name: '모델 관리 (MLOps)', path: '/mlops', icon: Cpu },
    { name: 'Data Lake & AI 계획', path: '/data-lake', icon: Database },
    { name: '조위 예측 기준선', path: '/forecasting', icon: Waves },
    { name: '알림 & 이슈', path: '/alerts', icon: AlertTriangle },
    { name: '시스템 관리', path: '/system', icon: Monitor },
  ];

  return (
    <div className={'flex h-screen bg-slate-50 text-slate-900 font-sans overflow-hidden relative '+(compactWorkspace?'observations-shell':'')}>
      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Left Sidebar (Dark Theme) */}
      <aside className={`platform-sidebar fixed lg:static inset-y-0 left-0 z-50 bg-[#0F172A] border-r border-slate-800 flex flex-col shrink-0 transform transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'w-20 collapsed' : 'w-64'} ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="p-5 flex flex-col items-center justify-center border-b border-slate-800 relative h-32">
          <Waves className={`text-blue-400 transition-all ${isSidebarCollapsed ? 'w-8 h-8 mb-0' : 'w-10 h-10 mb-3'}`} />
          {!isSidebarCollapsed && (
            <>
              <h1 className="text-sm font-bold text-slate-100 tracking-wide mt-2 text-center">해양관측 업무혁신 플랫폼</h1>
              <p className="text-[10px] text-slate-400 font-medium tracking-widest mt-1 text-center">OCEAN AI PLATFORM</p>
            </>
          )}
          <button
            className="absolute top-4 right-4 lg:hidden text-slate-400 hover:text-white"
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 py-6 space-y-1.5 px-3 overflow-y-auto custom-scrollbar-dark overflow-x-hidden">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = path === item.path || (path.startsWith(item.path) && item.path !== '/') || (item.path==='/qc'&&path==='/copilot');
            return (
              <Link
                key={item.name}
                to={item.path + contextQuery}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => setIsMobileMenuOpen(false)}
                title={`${item.name} · ${menuPurposeFor(item.path)?.purpose || ''}`}
                className={`flex items-center ${isSidebarCollapsed ? 'justify-center px-0' : 'gap-3 px-4'} py-3 rounded-lg transition-colors text-sm ${
                  isActive ? 'bg-blue-600 text-white font-bold' : 'text-slate-400 hover:bg-[#1E293B] hover:text-slate-200 font-medium'
                }`}
              >
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                {!isSidebarCollapsed && <span className="truncate whitespace-nowrap">{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 hidden lg:block">
          <div
            className={`flex items-center ${isSidebarCollapsed ? 'justify-center' : 'gap-2'} text-slate-400 hover:text-slate-200 cursor-pointer text-sm mb-4 transition-all`}
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          >
            <MenuSquare className="w-5 h-5 shrink-0" />
            {!isSidebarCollapsed && <span className="whitespace-nowrap">메뉴 접기</span>}
          </div>
          {!isSidebarCollapsed && (
            <div className="bg-[#1E293B] p-3 rounded-lg flex items-center justify-between cursor-pointer">
              <div className="flex flex-col">
                <span className="text-xs text-slate-300 font-medium">운영 안내</span>
                <span className="text-[10px] text-slate-500 mt-1">설정 및 실행 상태를 확인하세요.</span>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Area (Light Theme) */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[#F8FAFC] w-full">
        {!compactWorkspace&&<OperatorSession />}
        {/* Mobile Header */}
        <header className="lg:hidden h-14 bg-white border-b border-slate-200 flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-2">
            <Waves className="w-6 h-6 text-blue-600" />
            <h1 className="font-bold text-slate-800 text-sm">해양관측 플랫폼</h1>
          </div>
          <button onClick={() => setIsMobileMenuOpen(true)} className="p-2 -mr-2 text-slate-600">
            <Menu className="w-6 h-6" />
          </button>
        </header>

        <div className="flex-1 overflow-auto platform-content">
          {!compactWorkspace&&<WorkflowStatus />}
          {!compactWorkspace&&<MenuPurpose />}
          <Outlet />
          {compactWorkspace&&<details className="obs-access-panel"><summary>검토 환경·담당자 연결·업무 단계</summary><OperatorSession/><WorkflowStatus/><MenuPurpose/></details>}
        </div>
      </main>

      {/* AI Chatbot Floating Component */}
      <Chatbot />
    </div>
  );
};

export default Layout;
