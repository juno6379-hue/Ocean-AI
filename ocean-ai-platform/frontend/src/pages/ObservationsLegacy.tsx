import OSMBaseLayer from '../components/OSMBaseLayer';
// 파일 역할: 관측 현황과 관측소 위치를 표시합니다.
import { API_BASE_URL } from '../api/client';
import React, { useState, useEffect } from 'react';
import { apiClient as axios } from '../api/client';
import {
  Building2, CheckCircle, Clock, AlertTriangle,
  Database, RefreshCw, Bell, User, ChevronDown, Activity,
  Menu
} from 'lucide-react';
import { MapContainer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend
} from 'recharts';

const createCustomIcon = (status: string, name: string) => {
  let bgColor = 'bg-emerald-500';
  if (status === '지연') bgColor = 'bg-amber-500';
  if (status === '중단') bgColor = 'bg-red-500';

  return L.divIcon({
    className: 'custom-leaflet-icon',
    html: `
      <div class="flex flex-col items-center" style="transform: translate(-50%, 0);">
        <div class="w-4 h-4 rounded-full ${bgColor} border-2 border-white shadow-md"></div>
        <div class="text-[10px] font-bold text-slate-800 bg-white/90 px-1.5 py-0.5 rounded shadow-sm mt-0.5 whitespace-nowrap border border-slate-100">
          ${name}
        </div>
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 8],
  });
};

const Observations: React.FC = () => {
  const [summary, setSummary] = useState({
    total: 0, collection_rate: null as number | null, normal: 0, delay: 0, offline: 0, daily_count: 0
  });
  const [chartData, setChartData] = useState<any[]>([]);
  const [mapMarkers, setMapMarkers] = useState<any[]>([]);
  const [tableData, setTableData] = useState<any[]>([]);
  const [typeStatus, setTypeStatus] = useState<any[]>([]);
  const [recentData, setRecentData] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);

  // Table Filters
  const [filterNet, setFilterNet] = useState('전체 관측망');
  const [filterSea, setFilterSea] = useState('전체 해역');
  const [filterStat, setFilterStat] = useState('전체 상태');

  const uniqueNets = Array.from(new Set(tableData.map(row => row.net))).filter(Boolean);
  const uniqueSeas = Array.from(new Set(tableData.map(row => row.sea))).filter(Boolean);
  const uniqueStats = Array.from(new Set(tableData.map(row => row.stat))).filter(Boolean);

  const filteredTableData = tableData.filter(row => {
    if (filterNet !== '전체 관측망' && row.net !== filterNet) return false;
    if (filterSea !== '전체 해역' && row.sea !== filterSea) return false;
    if (filterStat !== '전체 상태' && row.stat !== filterStat) return false;
    return true;
  });

  // Map Filters
  const [filterMapSea, setFilterMapSea] = useState('전체 해역');
  const [filterMapNet, setFilterMapNet] = useState('전체 관측망');

  const uniqueMapSeas = Array.from(new Set(mapMarkers.map(m => m.sea))).filter(Boolean);
  const uniqueMapNets = Array.from(new Set(mapMarkers.map(m => m.net))).filter(Boolean);

  const filteredMapMarkers = mapMarkers.filter(m => {
    if (filterMapSea !== '전체 해역' && m.sea !== filterMapSea) return false;
    if (filterMapNet !== '전체 관측망' && m.net !== filterMapNet) return false;
    return true;
  });

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/observations/summary`);
        const d = res.data;
        if(d) {
          if (d.summary) setSummary(d.summary);
          if (d.chartData) setChartData(d.chartData);
          if (d.mapMarkers) setMapMarkers(d.mapMarkers);
          if (d.tableData) setTableData(d.tableData);
          if (d.typeStatus) setTypeStatus(d.typeStatus);
          if (d.recentData) setRecentData(d.recentData);
          if (d.notifications) setNotifications(d.notifications);
        }
      } catch(err) {
        console.error("Observations summary fetch error:", err);
      }
    };
    fetchSummary();
    const intervalId = setInterval(fetchSummary, 10000); // 10초 갱신
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="p-6 space-y-5 bg-[#F8FAFC] min-h-full">
      {/* Top Header */}
      <div className="flex justify-between items-end border-b border-slate-200 pb-4">
        <div className="flex items-end gap-4">
          <h2 className="text-2xl font-bold text-slate-900">관측 현황</h2>
          <p className="text-sm text-slate-500 mb-0.5">국가해양관측망 실시간 관측 및 수집 현황을 확인합니다.</p>
        </div>
        <div className="flex items-center gap-4 text-sm text-slate-600">
          <span>2025.05.28 (수) 10:30 KST</span>
          <button className="p-1.5 border border-slate-200 rounded hover:bg-slate-100"><RefreshCw className="w-4 h-4 text-slate-500" /></button>
          <div className="flex items-center border border-slate-200 rounded px-3 py-1.5 bg-white cursor-pointer hover:bg-slate-50">
            <span className="text-slate-500 mr-2">자동 갱신 |</span>
            <span className="font-medium mr-2">10초</span>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </div>
          <div className="w-px h-6 bg-slate-200 mx-1"></div>
          <div className="relative cursor-pointer">
            <Bell className="w-5 h-5 text-slate-500" />
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold w-4 h-4 flex items-center justify-center rounded-full">12</span>
          </div>
          <div className="flex items-center gap-2 cursor-pointer ml-2">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
            <div className="text-xs">
              <p className="font-bold text-slate-800">운영자</p>
              <p className="text-slate-500">관리자</p>
            </div>
          </div>
        </div>
      </div>

      {/* 6 Top Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <div className="bg-blue-50 p-1.5 rounded-lg"><Building2 className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">전체 관측소</span>
          </div>
          <p className="text-3xl font-black text-slate-800">{summary.total} <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>운영중 <span className="font-bold text-slate-700">{summary.total - summary.offline}</span></span>
            <span>정지 <span className="font-bold text-slate-700">{summary.offline}</span></span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <div className="bg-blue-50 p-1.5 rounded-lg"><Activity className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">실시간 수집률</span>
          </div>
          <p className="text-3xl font-black text-slate-800">{summary.collection_rate ?? '미산정'} <span className="text-sm font-normal text-slate-500">%</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>전일 대비</span>
            <span className="text-emerald-500 font-bold flex items-center gap-0.5">↑ 2.1%</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-emerald-500 mb-2">
            <div className="bg-emerald-50 p-1.5 rounded-lg"><CheckCircle className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">정상 수신 중</span>
          </div>
          <p className="text-3xl font-black text-slate-800">{summary.normal} <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>전일 대비</span>
            <span className="text-emerald-500 font-bold">↑ 3</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-amber-500 mb-2">
            <div className="bg-amber-50 p-1.5 rounded-lg"><Clock className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">수신 지연</span>
          </div>
          <p className="text-3xl font-black text-slate-800">{summary.delay} <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>전일 대비</span>
            <span className="text-amber-500 font-bold">↓ 1</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-red-500 mb-2">
            <div className="bg-red-50 p-1.5 rounded-lg"><AlertTriangle className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">수신 중단</span>
          </div>
          <p className="text-3xl font-black text-slate-800">{summary.offline} <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>전일 대비</span>
            <span className="text-amber-500 font-bold">↓ 1</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <div className="bg-blue-50 p-1.5 rounded-lg"><Database className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">관측 데이터 건수(금일)</span>
          </div>
          <p className="text-3xl font-black text-slate-800">{summary.daily_count.toLocaleString()} <span className="text-sm font-normal text-slate-500">건</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>전일 대비</span>
            <span className="text-emerald-500 font-bold">↑ 45,231</span>
          </div>
        </div>
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">

        {/* Left Col - Map & Line Chart */}
        <div className="xl:col-span-1 flex flex-col gap-5">
          {/* Map */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[400px]">
            <h3 className="text-sm font-bold text-slate-800 mb-3">관측소 위치 및 상태 지도</h3>
            <div className="flex-1 rounded-lg overflow-hidden border border-slate-200 relative">
              <MapContainer center={[36.5, 127.5]} zoom={6} style={{ height: '100%', width: '100%' }} zoomControl={false}>
                <OSMBaseLayer/>
                {filteredMapMarkers.map((marker, i) => (
                  <Marker key={i} position={[marker.lat, marker.lng]} icon={createCustomIcon(marker.status, marker.name)}>
                    <Popup>
                      <div className="text-xs font-bold">{marker.name}</div>
                      <div className="text-[10px] text-slate-500">{marker.sea} | {marker.net} ({marker.network_code})</div>
                      <div className="text-[10px] font-bold mt-1">상태: {marker.status}</div>
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
              {/* Legend overlay */}
              <div className="absolute top-3 right-3 bg-slate-900/80 backdrop-blur-sm p-2 rounded border border-slate-700 text-[10px] text-slate-300 z-[400]">
                <div className="flex items-center gap-1.5 mb-1"><div className="w-2 h-2 rounded-full bg-emerald-500"></div> 정상</div>
                <div className="flex items-center gap-1.5 mb-1"><div className="w-2 h-2 rounded-full bg-amber-500"></div> 지연</div>
                <div className="flex items-center gap-1.5 mb-1"><div className="w-2 h-2 rounded-full bg-red-500"></div> 중단</div>
                <div className="flex items-center gap-1.5 mb-1"><div className="w-2 h-2 rounded-full bg-slate-500"></div> 정지</div>
                <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-blue-500"></div> 점검</div>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3 text-xs">
              <select value={filterMapSea} onChange={e => setFilterMapSea(e.target.value)} className="border border-slate-200 rounded px-2 py-1.5 flex-1 bg-white outline-none">
                <option value="전체 해역">전체 해역</option>
                {uniqueMapSeas.map(sea => <option key={sea as string} value={sea as string}>{sea as string}</option>)}
              </select>
              <select value={filterMapNet} onChange={e => setFilterMapNet(e.target.value)} className="border border-slate-200 rounded px-2 py-1.5 flex-1 bg-white outline-none">
                <option value="전체 관측망">전체 관측망</option>
                {uniqueMapNets.map(net => <option key={net as string} value={net as string}>{net as string}</option>)}
              </select>
              <button className="text-blue-600 font-medium px-2 py-1.5 hover:bg-blue-50 rounded">전체 목록 보기</button>
            </div>
          </div>

          {/* Line Chart */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[300px] flex flex-col">
            <h3 className="text-sm font-bold text-slate-800 mb-4">시간대별 수집률 추이 <span className="text-xs font-normal text-slate-500">(최근 24시간)</span></h3>
            <div className="flex-1 w-full text-xs">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fill: '#64748B'}} />
                  <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{fill: '#64748B'}} width={30} />
                  <RechartsTooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Legend iconType="plainline" wrapperStyle={{ fontSize: '11px', top: -10 }} />
                  <Line type="monotone" dataKey="total" name="전체" stroke="#3B82F6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="tide" name="조위" stroke="#10B981" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                  <Line type="monotone" dataKey="weather" name="기상" stroke="#A855F7" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                  <Line type="monotone" dataKey="ocean" name="해양" stroke="#F59E0B" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Middle Col - Table & Progress Bars */}
        <div className="xl:col-span-2 flex flex-col gap-5">
          {/* Table */}
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[400px]">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-bold text-slate-800">관측소 실시간 수집 현황</h3>
              <div className="flex gap-2 text-xs">
                <select value={filterNet} onChange={e => setFilterNet(e.target.value)} className="border border-slate-200 rounded px-2 py-1 bg-white outline-none text-slate-600">
                  <option value="전체 관측망">전체 관측망</option>
                  {uniqueNets.map(net => <option key={net as string} value={net as string}>{net as string}</option>)}
                </select>
                <select value={filterSea} onChange={e => setFilterSea(e.target.value)} className="border border-slate-200 rounded px-2 py-1 bg-white outline-none text-slate-600">
                  <option value="전체 해역">전체 해역</option>
                  {uniqueSeas.map(sea => <option key={sea as string} value={sea as string}>{sea as string}</option>)}
                </select>
                <select value={filterStat} onChange={e => setFilterStat(e.target.value)} className="border border-slate-200 rounded px-2 py-1 bg-white outline-none text-slate-600">
                  <option value="전체 상태">전체 상태</option>
                  {uniqueStats.map(stat => <option key={stat as string} value={stat as string}>{stat as string}</option>)}
                </select>
                <button className="border border-slate-200 rounded px-2 py-1 text-slate-600 hover:bg-slate-50"><Menu className="w-3.5 h-3.5" /></button>
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-slate-500 bg-slate-50 border-y border-slate-200 sticky top-0">
                  <tr>
                    <th className="py-2.5 px-3 font-medium">관측소명</th>
                    <th className="py-2.5 px-3 font-medium">관측망</th>
                    <th className="py-2.5 px-3 font-medium">해역</th>
                    <th className="py-2.5 px-3 font-medium text-right">수집률(%)</th>
                    <th className="py-2.5 px-3 font-medium text-center">수신 상태</th>
                    <th className="py-2.5 px-3 font-medium text-center">최근 데이터 시간(KST)</th>
                    <th className="py-2.5 px-3 font-medium text-center">지연 시간</th>
                    <th className="py-2.5 px-3 font-medium">비고</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {filteredTableData.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                      <td className="py-2.5 px-3 font-medium text-slate-800">{row.name}</td>
                      <td className="py-2.5 px-3">{row.net}</td>
                      <td className="py-2.5 px-3">{row.sea}</td>
                      <td className="py-2.5 px-3 text-right">{row.rate}</td>
                      <td className={`py-2.5 px-3 text-center font-bold ${row.statColor}`}>{row.stat}</td>
                      <td className="py-2.5 px-3 text-center">{row.time}</td>
                      <td className="py-2.5 px-3 text-center">{row.delay}</td>
                      <td className="py-2.5 px-3 text-xs text-slate-500">{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 text-center border-t border-slate-100 pt-3">
              <button className="text-xs text-blue-600 font-medium hover:underline">전체 관측소 현황 보기 →</button>
            </div>
          </div>

          {/* Bottom Right Layout Split: Progress Bars & Lists */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 h-[300px]">
            {/* Progress Bars */}
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col">
              <h3 className="text-sm font-bold text-slate-800 mb-4">관측항목별 수신 현황</h3>
              <div className="flex-1 overflow-auto space-y-3.5 text-xs pr-2">
                {typeStatus.map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="w-10 font-medium text-slate-700">{item.name}</span>
                    <div className="flex-1 bg-slate-100 h-2.5 rounded-full overflow-hidden flex items-center relative">
                      <div className={`h-full ${item.color} rounded-full`} style={{ width: `${item.rate}%` }}></div>
                      <span className="absolute right-1 text-[9px] font-bold text-slate-600 translate-x-8">{item.rate}</span>
                    </div>
                    <span className={`w-8 text-right font-bold ${item.statColor}`}>{item.stat}</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 text-center border-t border-slate-100 pt-2">
                <button className="text-xs text-blue-600 font-medium hover:underline">전체 항목 현황 보기 →</button>
              </div>
            </div>

            {/* Notifications & Lists */}
            <div className="flex flex-col gap-5">
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex-1 overflow-hidden flex flex-col">
                <h3 className="text-sm font-bold text-slate-800 mb-3">최근 데이터 수신 현황</h3>
                <div className="flex-1 overflow-y-auto space-y-4 text-xs pr-2">
                  {(Object.entries(
                    recentData.reduce((acc, item) => {
                      const net = item.network_type || '기타';
                      if (!acc[net]) acc[net] = [];
                      acc[net].push(item);
                      return acc;
                    }, {} as Record<string, any[]>)
                  ) as [string, any[]][]).map(([network, items]) => (
                    <div key={network} className="space-y-1.5">
                      <div className="text-[11px] font-bold text-slate-500 border-b border-slate-100 pb-1 mb-1">{network}</div>
                      {items.map((item, i) => (
                        <div key={i} className="flex justify-between items-center p-1 hover:bg-slate-50 rounded">
                          <span className="font-medium text-slate-700">{item.name}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-slate-400 text-[10px]">{item.time}</span>
                            <span className={`${item.color} font-bold w-10 text-right`}>{item.status}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex-1 overflow-hidden flex flex-col">
                <h3 className="text-sm font-bold text-slate-800 mb-3">수신 알림</h3>
                <div className="flex-1 overflow-y-auto space-y-3">
                  {notifications.map((notif, i) => (
                    <div key={i} className="flex gap-2">
                      <div className={`w-2 h-2 mt-1 rounded-full ${notif.dot_color} shrink-0`}></div>
                      <div className="flex-1">
                        <div className="flex justify-between text-xs font-bold text-slate-800">
                          <span>{notif.title}</span>
                          <span className="text-slate-500 font-normal">{notif.time}</span>
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">{notif.message}</div>
                      </div>
                    </div>
                  ))}
                  {notifications.length === 0 && (
                     <div className="text-xs text-slate-400 text-center mt-4">현재 새로운 알림이 없습니다.</div>
                  )}
                </div>
                <div className="mt-2 text-center border-t border-slate-100 pt-2">
                  <button className="text-[11px] text-blue-600 font-medium hover:underline">전체 알림 보기 →</button>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default Observations;
