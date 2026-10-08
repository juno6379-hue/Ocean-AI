import OSMBaseLayer from '../components/OSMBaseLayer';
// 파일 역할: 관측 및 품질관리 통합 현황을 표시합니다.
import { apiFetch } from '../api/client';
import { API_BASE_URL } from '../api/client';
import React, { useEffect, useState } from 'react';
import { apiClient as axios } from '../api/client';
import {
  Building2, Activity, CheckCircle, Bug, AlertTriangle, FileText,
  ChevronRight
} from 'lucide-react';
import { MapContainer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer
} from 'recharts';

const createCustomIcon = (status: string) => {
  const color = status === '정상' ? '#10B981' : status === '주의' ? '#F59E0B' : status === '경고' ? '#EF4444' : '#64748B';
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div style="background-color: ${color}; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.2);"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7]
  });
};

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [summaryData, setSummaryData] = useState<any>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const [timeRange, setTimeRange] = useState('실시간');

  // DB Fetched Data
  const [modelData, setModelData] = useState<any[]>([]);
  const [loadError, setLoadError] = useState('');
  const [mlopsAlerts, setMlopsAlerts] = useState<any[]>([]);
  const [recentReports, setRecentReports] = useState<any[]>([]);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (date: Date) => {
    const days = ['일', '월', '화', '수', '목', '금', '토'];
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const day = days[date.getDay()];
    const h = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    const s = String(date.getSeconds()).padStart(2, '0');
    return `${y}.${m}.${d} (${day}) ${h}:${min}:${s} KST`;
  };

  useEffect(() => {
    const fetchPartA = async () => {
      try {
        const perfRes = await axios.get(`${API_BASE_URL}/dashboard/performance`);
        if (perfRes.data.perfTrendData) {
           setModelData(perfRes.data.perfTrendData.map((d: any) => ({ date: d.version, rmse: d.rmse, f1: d.f1 })));
        }

        const alertRes = await axios.get(`${API_BASE_URL}/qc/alerts`);
        if (alertRes.data.alerts) {
           setMlopsAlerts(alertRes.data.alerts.map((a: any) => ({
             text: a.text,
             state: a.status === 'ANOMALY' ? '심각' : '주의',
             stateColor: a.status === 'ANOMALY' ? 'bg-red-100 text-red-600 border-red-200' : 'bg-amber-100 text-amber-600 border-amber-200',
             desc: a.sub,
             time: a.time
           })));
        }

        const repRes = await axios.get(`${API_BASE_URL}/reports/list`);
        if (repRes.data.reports) {
           setRecentReports(repRes.data.reports.slice(0,4).map((r: any) => ({
             title: r.title,
             time: r.date
           })));
        }
        setLastSynced(new Date());
      } catch (e) { console.error(e); }
    };
    fetchPartA();
    const interval = setInterval(fetchPartA, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await apiFetch(`${API_BASE_URL}/dashboard/summary`);
        if (!res.ok) throw new Error(`API ${res.status}`);
        const data = await res.json();
        if (data.success) {
          setSummaryData(data);
        }
      } catch (err) {
        console.error('Error fetching dashboard summary:', err);
        setLoadError('대시보드 API 연결에 실패했습니다. 서버 실행 상태를 확인하세요.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="flex h-full items-center justify-center text-blue-600">데이터 로딩 중...</div>;

  const timeTabs = ['실시간', '1시간', '6시간', '24시간'];

  const getPastWeekRange = () => {
    const today = new Date();
    const past = new Date(today);
    past.setDate(past.getDate() - 7);
    return `${past.getFullYear()}-${String(past.getMonth()+1).padStart(2,'0')}-${String(past.getDate()).padStart(2,'0')} ~ ${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
  };

  return (
    <div className="p-4 md:p-6 space-y-5 bg-[#F8FAFC] min-h-full">
      {loadError && <p role="alert" className="text-red-700">{loadError}</p>}
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm">이 화면은 운영 PostgreSQL에 적재된 자료를 집계합니다. D:의 월별 Parquet 검증 현황과 원천 조회는 <a className="font-bold underline" href="/data-lake">Data Lake 자료 검증</a>에서 확인하세요. 두 범위의 건수와 QC 판정은 별개입니다.</div>
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">통합 대시보드</h2>
          <p className="text-sm text-slate-500 mt-1">해양관측 전체 현황을 한눈에 확인하세요.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="text-slate-500 hidden sm:inline-block font-mono tracking-tight">{formatTime(currentTime)}</span>
          <div className="flex bg-slate-100 rounded-md border border-slate-200 p-0.5">
            {timeTabs.map(tab => (
              <button
                key={tab}
                onClick={() => setTimeRange(tab)}
                className={`px-3 py-1.5 rounded transition-all duration-200 ${timeRange === tab ? 'bg-white text-blue-600 font-bold shadow-sm' : 'text-slate-600 hover:text-slate-900 font-medium'}`}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 text-slate-700 font-medium rounded-md shadow-sm">
            <div className={`w-2 h-2 rounded-full ${lastSynced ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`}></div>
            <span className="text-xs">{lastSynced ? '실시간 연동 중' : '연결 대기'}</span>
          </div>
        </div>
      </div>

      {/* Top 6 Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {[
          { title: '전체 관측소 (DB)', val: summaryData?.total_stations || 0, unit: '개소', icon: Building2, color: 'text-blue-600', bg: 'bg-blue-50', sub1: '운영중', sub1V: summaryData?.total_stations || 0, sub2: '정지', sub2V: '0' },
          { title: '수집률 (DB)', val: summaryData?.data_collection_rate ?? '미산정', unit: '%', icon: Activity, color: 'text-blue-600', bg: 'bg-blue-50', diffText: '예정 수집건수 필요', diffVal: '-', diffColor: 'text-emerald-500' },
          { title: 'QC 정상 비율 (DB)', val: summaryData?.qc_normal_rate || 0, unit: '%', icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-50', diffText: '양호', diffVal: '-', diffColor: 'text-emerald-500' },
          { title: 'BAD 비율 (DB)', val: summaryData?.bad_rate || 0, unit: '%', icon: Bug, color: 'text-red-500', bg: 'bg-red-50', diffText: '경고 발생', diffVal: '-', diffColor: 'text-red-500' },
          { title: '이상 알림', val: '12', unit: '건', icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50', diffText: '미조치', diffVal: '5건', diffColor: 'text-slate-600' },
          { title: 'AI 분석 리포트', val: '8', unit: '건', icon: FileText, color: 'text-purple-500', bg: 'bg-purple-50', diffText: '생성 완료', diffVal: '', diffColor: 'text-slate-600' },
        ].map((card, i) => (
          <div key={i} className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
            <div className="flex items-center gap-2 mb-2">
              <div className={`${card.bg} p-1.5 rounded-lg`}><card.icon className={`w-5 h-5 ${card.color}`} /></div>
              <p className="text-xs font-bold text-slate-700 truncate">{card.title}</p>
            </div>
            <div>
              <p className={`text-2xl font-black ${i === 4 ? 'text-red-500' : 'text-slate-800'}`}>{card.val} <span className="text-sm font-normal text-slate-500">{card.unit}</span></p>
              <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
                {card.sub1 ? (
                  <>
                    <span>{card.sub1} <span className="font-bold text-slate-700">{card.sub1V}</span></span>
                    <span>{card.sub2} <span className="font-bold text-slate-700">{card.sub2V}</span></span>
                  </>
                ) : (
                  <>
                    <span>{card.diffText}</span>
                    <span className={`font-bold ${card.diffColor}`}>{card.diffVal}</span>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Middle Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Map */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[360px] lg:h-[400px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">관측소 현황 지도</h3>
          <div className="flex items-center gap-3 text-[10px] mb-2 text-slate-600">
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-500"></div> 정상</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-amber-500"></div> 주의</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-red-500"></div> 경고</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-slate-500"></div> 정지</span>
          </div>
          <div className="flex-1 rounded-lg overflow-hidden border border-slate-200 relative z-0">
            <MapContainer center={[36.5, 127.5]} zoom={6} style={{ height: '100%', width: '100%', background: '#F8FAFC' }} zoomControl={false}>
              <OSMBaseLayer/>
              {summaryData?.station_summary?.filter((station: any) => station.latitude && station.longitude).map((station: any) => (
                <Marker
                  key={station.station_id}
                  position={[station.latitude, station.longitude]}
                  icon={createCustomIcon(station.qc === '경고' ? '경고' : '정상')}
                >
                  <Popup>
                    <strong>{station.name}</strong><br />
                    해역: {station.sea_area || '미상'}<br />
                    관측망: {station.network_type} ({station.network_code})<br />
                    관측소 코드: {station.station_id}
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
          <button className="w-full text-xs text-blue-600 font-medium hover:underline mt-3 flex justify-center items-center gap-1">전체 관측소 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Table */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[360px] lg:h-[400px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">실시간 해양 관측 요약</h3>
          <div className="flex gap-2 border-b border-slate-200 mb-2 overflow-x-auto custom-scrollbar pb-1">
            <button className="px-3 py-1.5 text-xs font-bold text-blue-600 border-b-2 border-blue-600 whitespace-nowrap">조위</button>
            <button className="px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 whitespace-nowrap">수온</button>
            <button className="px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 whitespace-nowrap">파고</button>
            <button className="px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 whitespace-nowrap">기압</button>
            <button className="px-3 py-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 whitespace-nowrap">유속</button>
          </div>
          <div className="flex-1 overflow-auto">
            <table className="w-full text-xs text-left min-w-[300px]">
              <thead className="text-slate-500 bg-slate-50 border-b border-slate-200 sticky top-0">
                <tr>
                  <th className="py-2.5 px-2 font-medium">관측소</th>
                  <th className="py-2.5 px-2 font-medium">조위(cm)</th>
                  <th className="py-2.5 px-2 font-medium">수집률</th>
                  <th className="py-2.5 px-2 font-medium">QC 상태</th>
                  <th className="py-2.5 px-2 font-medium text-right">전일 대비</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {summaryData?.station_summary?.map((row: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-2">{row.name}</td>
                    <td className="py-2.5 px-2 font-bold">{row.val}</td>
                    <td className="py-2.5 px-2">{row.rate}</td>
                    <td className="py-2.5 px-2"><span className={`px-2 py-0.5 border rounded-full text-[10px] font-bold ${row.qcColor}`}>{row.qc}</span></td>
                    <td className={`py-2.5 px-2 text-right font-medium ${row.diffColor}`}>{row.diff}</td>
                  </tr>
                ))}
                {(!summaryData || !summaryData.station_summary || summaryData.station_summary.length === 0) && (
                   <tr><td colSpan={5} className="text-center py-4 text-slate-400">데이터가 없습니다.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <button className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-2 border-t border-slate-100">전체 관측 데이터 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Donut Chart */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[360px] lg:h-[400px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">QC (품질관리) 현황</h3>
          <div className="flex-1 flex flex-col md:flex-row items-center justify-between">
            <div className="w-full md:w-1/2 h-48 md:h-full relative flex justify-center items-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={summaryData?.qc_pie_data || []} innerRadius={60} outerRadius={85} dataKey="value" stroke="none">
                    {(summaryData?.qc_pie_data || []).map((entry: any, index: number) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute text-center flex flex-col items-center justify-center pointer-events-none">
                <p className="text-[10px] text-slate-500 font-medium">전체 데이터</p>
                <p className="text-xl font-black text-slate-800">
                  {summaryData?.qc_pie_data?.reduce((acc: number, cur: any) => acc + cur.value, 0).toLocaleString() || 0}
                </p>
                <p className="text-[10px] text-slate-500">건</p>
              </div>
            </div>
            <div className="w-full md:w-1/2 space-y-4 md:pl-6 mt-4 md:mt-0">
              {(summaryData?.qc_pie_data || []).map((item: any, i: number) => {
                const total = summaryData.qc_pie_data.reduce((acc: number, cur: any) => acc + cur.value, 0);
                const percent = total > 0 ? ((item.value / total) * 100).toFixed(1) : '0.0';
                return (
                <div key={i} className="flex justify-between items-center text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></div>
                    <span className="text-slate-700 font-medium">{item.name}</span>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-slate-900">{percent}%</p>
                    <p className="text-[10px] text-slate-500">{item.value.toLocaleString()}건</p>
                  </div>
                </div>
              )})}
            </div>
          </div>
          <button className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-3 border-t border-slate-100">품질 현황 상세 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Alerts */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[260px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-slate-800">AI 이상 탐지 알림</h3>
            <span className="bg-red-100 text-red-600 text-[10px] px-2 py-0.5 rounded-full font-bold">5건</span>
          </div>
          <div className="flex-1 overflow-auto space-y-2.5 pr-1">
            {mlopsAlerts.map((alert, i) => (
              <div key={i} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg text-xs border border-slate-100 hover:bg-slate-100 transition-colors">
                <div className="flex items-center gap-2">
                  <div className="p-1 bg-white border border-slate-200 rounded"><AlertTriangle className="w-3.5 h-3.5 text-red-500" /></div>
                  <span className="font-bold text-slate-700">{alert.text}</span>
                  <span className={`px-1.5 py-0.5 border rounded text-[10px] ${alert.stateColor}`}>{alert.state}</span>
                </div>
                <div className="flex items-center gap-4 text-slate-500">
                  <span className="hidden sm:inline-block">{alert.desc}</span>
                  <span>{alert.time}</span>
                </div>
              </div>
            ))}
          </div>
          <button className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-3 border-t border-slate-100">전체 알림 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Reports */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[260px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2"><FileText className="w-4 h-4 text-purple-600" /> 최근 AI 분석 리포트</h3>
          </div>
          <div className="flex-1 overflow-auto space-y-2.5 pr-1">
            {recentReports.map((report, i) => (
              <div key={i} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg text-xs border border-slate-100 hover:bg-slate-100 transition-colors">
                <div className="flex items-center gap-2">
                  <div className="p-1 bg-white border border-slate-200 rounded"><FileText className="w-3.5 h-3.5 text-purple-600" /></div>
                  <span className="font-bold text-slate-700 truncate max-w-[150px] sm:max-w-[200px]">{report.title}</span>
                </div>
                <span className="text-slate-500 whitespace-nowrap">{report.time}</span>
              </div>
            ))}
          </div>
          <button className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-3 border-t border-slate-100">전체 리포트 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Model Performance */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[260px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-slate-800">모델 성능 요약</h3>
            <select className="bg-white border border-slate-200 text-xs px-2 py-1.5 rounded text-slate-600 outline-none">
              <option>{getPastWeekRange()}</option>
            </select>
          </div>
          <div className="flex flex-col sm:flex-row gap-4 mb-2 flex-1">
            <div className="flex flex-row sm:flex-col justify-between sm:justify-start gap-4 sm:w-1/3">
              <div>
                <p className="text-[10px] text-slate-500 font-medium">RMSE (평균)</p>
                <p className="text-2xl font-black text-slate-800">3.42</p>
                <p className="text-[10px] font-bold text-emerald-500">전주 대비 ↑ 0.18</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 font-medium">F1 Score (평균)</p>
                <p className="text-2xl font-black text-slate-800">0.82</p>
                <p className="text-[10px] font-bold text-emerald-500">전주 대비 ↑ 0.05</p>
              </div>
            </div>
            <div className="flex-1 h-32 sm:h-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={modelData}>
                  <XAxis dataKey="date" tick={{fontSize: 9, fill: '#64748B'}} stroke="#E2E8F0" axisLine={false} tickLine={false} />
                  <YAxis yAxisId="left" tick={{fontSize: 9, fill: '#64748B'}} stroke="#E2E8F0" axisLine={false} tickLine={false} domain={[0, 5]} width={20} />
                  <YAxis yAxisId="right" orientation="right" tick={{fontSize: 9, fill: '#64748B'}} stroke="#E2E8F0" axisLine={false} tickLine={false} domain={[0, 1]} width={20} />
                  <RechartsTooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #E2E8F0', borderRadius: '8px', fontSize: '11px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Line yAxisId="left" type="monotone" dataKey="rmse" stroke="#3B82F6" strokeWidth={2} dot={{r:3}} name="RMSE" />
                  <Line yAxisId="right" type="monotone" dataKey="f1" stroke="#A855F7" strokeWidth={2} dot={{r:3}} name="F1 Score" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <button className="w-full text-xs text-blue-600 font-medium hover:underline mt-auto pt-3 flex justify-center items-center gap-1 border-t border-slate-100">모델 관리 (MLOps) <ChevronRight className="w-3 h-3"/></button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
