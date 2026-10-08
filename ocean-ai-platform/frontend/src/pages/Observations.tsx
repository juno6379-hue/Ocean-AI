import StationClassifications, { DatasetSourceSelect } from '../components/StationClassifications';
import OSMBaseLayer from '../components/OSMBaseLayer';
import StationQuickView from '../components/StationQuickView';
// 파일 역할: 관측 현황과 관측소 위치를 표시합니다.
import { API_BASE_URL, apiFetch } from '../api/client';
import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Building2, CheckCircle, Clock, AlertTriangle,
  Database, RefreshCw, Bell, Activity,
  Menu
} from 'lucide-react';
import { MapContainer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend
} from 'recharts';

const createCustomIcon = (status: string, name: string) => {
  let bgColor = 'bg-slate-500';
  // Escape source names before passing them to Leaflet's HTML icon renderer.
  const safeName = name.replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]!));
  if (status === '지연') bgColor = 'bg-amber-500';
  if (status === '중단') bgColor = 'bg-red-500';

  return L.divIcon({
    className: 'custom-leaflet-icon',
    html: `
      <div class="flex flex-col items-center" style="transform: translate(-50%, 0);">
        <div class="w-4 h-4 rounded-full ${bgColor} border-2 border-white shadow-md"></div>
        <div class="text-[10px] font-bold text-slate-800 bg-white/90 px-1.5 py-0.5 rounded shadow-sm mt-0.5 whitespace-nowrap border border-slate-100">
          ${safeName}
        </div>
      </div>
    `,
    iconSize: [0, 0],
    iconAnchor: [0, 8],
  });
};

const Observations: React.FC = () => {
  const [summary, setSummary] = useState<{total: number | null; held_rows: number | null; items: number | null}>({total:null, held_rows:null, items:null});
  const [selectedStation, setSelectedStation] = useState('');
  const [lake, setLake] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [metadataError, setMetadataError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);
  const [refreshSeconds, setRefreshSeconds] = useState(0);
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const source = search.get('source') || 'GD_OBS_ST_MONTHLY';
  const from = search.get('from') || (source === 'HISTORICAL_RECONCILED' ? '2011-01' : '2023-01');
  const to = search.get('to') || (source === 'HISTORICAL_RECONCILED' ? '2021-12' : '2026-07');
  const query = new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source, from_month:from, to_month:to}).toString();
  const linkQuery = new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source, from, to}).toString();
  const update = (changes: Record<string, string>) => setSearch({...Object.fromEntries(search), ...changes});
  const [stationSearch, setStationSearch] = useState('');
  const [chartData, setChartData] = useState<any[]>([]);
  const [mapMarkers, setMapMarkers] = useState<any[]>([]);
  const [tableData, setTableData] = useState<any[]>([]);
  const [typeStatus, setTypeStatus] = useState<any[]>([]);
  const [recentData, setRecentData] = useState<any[]>([]);
  const [notifications] = useState<any[]>([]);

  // Table Filters
  const [filterNet, setFilterNet] = useState('전체 관측망');
  const [filterSea, setFilterSea] = useState('전체 해역');
  const [filterStat, setFilterStat] = useState('전체 상태');

  const uniqueStats = Array.from(new Set(tableData.map(row => row.stat))).filter(Boolean);

  const filteredTableData = tableData.filter(row => {
    if (!`${row.name} ${row.id}`.toLowerCase().includes(stationSearch.toLowerCase())) return false;
    if (filterNet !== '전체 관측망' && row.net !== filterNet) return false;
    if (filterSea !== '전체 해역' && row.sea !== filterSea) return false;
    if (filterStat !== '전체 상태' && row.stat !== filterStat) return false;
    return true;
  });

  // Map Filters
  const [filterMapSea, setFilterMapSea] = useState('전체 해역');
  const [filterMapNet, setFilterMapNet] = useState('전체 관측망');


  const filteredMapMarkers = mapMarkers.filter(m => {
    if (filterMapSea !== '전체 해역' && m.sea !== filterMapSea) return false;
    if (filterMapNet !== '전체 관측망' && m.net !== filterMapNet) return false;
    return true;
  });

  useEffect(() => {
    if (!refreshSeconds) return;
    const timer = setInterval(() => setRevision(r => r + 1), refreshSeconds * 1000);
    return () => clearInterval(timer);
  }, [refreshSeconds]);

  useEffect(() => {
    const control = new AbortController();
    // Never leave values from the previous source/period visible under new filters.
    setSelectedStation('');
    setLoading(true); setError(''); setMetadataError(''); setLake(null); setLastUpdated(null);
    setSummary({total:null, held_rows:null, items:null}); setChartData([]); setMapMarkers([]);
    setTableData([]); setTypeStatus([]); setRecentData([]);
    const read = async (path: string) => {
      const r = await apiFetch(`${API_BASE_URL}${path}`, {signal:control.signal});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    };
    if (from > to) { setError('시작월은 종료월보다 늦을 수 없습니다.'); setLoading(false); return () => control.abort(); }
    Promise.all([
      read(`/lake/summary?${query}`),
      read('/stations?limit=10000').catch(() => {if (!control.signal.aborted) setMetadataError('지도 기준정보 조회 실패'); return []; }),
    ]).then(([data, metadata]) => {
      if (control.signal.aborted) return;
      const references = new Map<string, any[]>();
      for (const m of metadata) references.set(m.station_id, [...(references.get(m.station_id) || []), m]);
      const rows = data.stations.map((r: any) => {
        // Codes are selected from the Parquet catalog. Existing SQL metadata only supplies reference coordinates.
        const matches = references.get(r.station_code) || [];
        const ref = matches.length === 1 ? matches[0] : null;
        const valid = Number.isFinite(ref?.latitude) && Number.isFinite(ref?.longitude)
          && Math.abs(ref.latitude) <= 90 && Math.abs(ref.longitude) <= 180;
        return {id:r.station_code, name:r.station_name || r.station_code,
          net:ref ? (ref.network_type || 'DB 분류값 없음') : 'DB 기준정보 미등록', sea:ref ? (ref.sea_area || 'DB 해역값 없음') : 'DB 기준정보 미등록',
          lat:valid ? ref.latitude : null, lng:valid ? ref.longitude : null,
          rate:'미산정', stat:'미확정', status:'미확정', statColor:'text-slate-500',
          time:r.last_clock || '미확정', first:r.first_clock, delay:'미산정',
          note:`${r.held_rows.toLocaleString('ko-KR')}행 · ${r.items}항목 · ${r.held_months}개월`,
          held_rows:r.held_rows, items:r.items, months:r.held_months};
      });
      setLake(data); setSummary({total:data.totals.stations, held_rows:data.totals.held_rows, items:data.totals.items});
      setSelectedStation(rows[0]?.id || '');
      setTableData(rows); setMapMarkers(rows.filter((r:any) => r.lat != null && r.lng != null));
      const monthRows = new Map<string, number>(data.monthly.map((m:any) => [String(m.month).slice(0,7), m.held_rows]));
      const months = [];
      const [year, month] = from.split('-').map(Number);
      let cursor = new Date(Date.UTC(year, month-1, 1));
      // Missing months remain null so the chart does not imply continuous observation or zero observations.
      while (cursor.toISOString().slice(0,7) <= to && months.length < 1200) {
        const key = cursor.toISOString().slice(0,7);
        months.push({time:key, total:monthRows.get(key) ?? null});
        cursor.setUTCMonth(cursor.getUTCMonth()+1);
      }
      setChartData(months);
      const maxItems = Math.max(1, ...rows.map((r:any) => r.items));
      setTypeStatus([...rows].sort((a:any,b:any) => b.items-a.items).map((r:any) => ({
        id:r.id, name:r.name, rate:r.items/maxItems*100, stat:`${r.items}개`, color:'bg-blue-500', statColor:'text-slate-600',
      })));
      setRecentData([...rows].filter((r:any) => r.time !== '미확정').sort((a:any,b:any) => b.time.localeCompare(a.time)).slice(0,10).map((r:any) => ({
        ...r, network_type:r.net, color:'text-slate-500', status:'보유',
      })));
      setLastUpdated(new Date());
    }).catch(e => {if (!control.signal.aborted) setError(`실측자료 조회 실패: ${e.message}`);})
      .finally(() => {if (!control.signal.aborted) setLoading(false);});
    return () => control.abort();
  }, [query, revision]);

  useEffect(() => {
    setFilterNet('전체 관측망'); setFilterSea('전체 해역'); setFilterStat('전체 상태');
    setFilterMapSea('전체 해역'); setFilterMapNet('전체 관측망'); setStationSearch('');
  }, [query]);

  const resetTable = () => {setFilterNet('전체 관측망'); setFilterSea('전체 해역'); setFilterStat('전체 상태'); setStationSearch(''); document.getElementById('observation-table')?.scrollIntoView({behavior:'smooth'});};

  return (
    <div className="p-6 space-y-5 bg-gradient-to-br from-blue-50/60 via-white to-indigo-50/40 min-h-full">
      {/* Top Header */}
      <div className="flex flex-wrap gap-3 justify-between items-end border-b border-slate-200 pb-4">
        <div className="flex flex-wrap items-end gap-4">
          <h2 className="text-3xl font-extrabold text-slate-900">관측 현황</h2>
          <p className="text-sm text-slate-500 mb-0.5">국가해양관측망의 보유 자료와 관측기간을 확인합니다.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
          <span>{lastUpdated ? `조회 ${lastUpdated.toLocaleTimeString('ko-KR', {timeZone:'Asia/Seoul'})} KST` : '조회 대기'}</span>
          <button aria-label="새로고침" onClick={() => setRevision(r=>r+1)} disabled={loading} className="p-1.5 border border-slate-200 rounded hover:bg-slate-100"><RefreshCw className="w-4 h-4"/></button>
          <label>화면 갱신 <select aria-label="자동 갱신" value={refreshSeconds} onChange={e=>setRefreshSeconds(Number(e.target.value))} className="border border-slate-200 rounded px-2 py-1.5 bg-white"><option value={0}>수동</option><option value={60}>1분</option><option value={300}>5분</option></select></label>
          <button aria-label="알림 메뉴" onClick={()=>navigate('/alerts')} className="p-1.5"><Bell className="w-5 h-5"/></button>
        </div>
      </div>
    <StationClassifications/>
      <div className="flex flex-wrap gap-3 items-center text-xs">
        <label>원천 <DatasetSourceSelect source={source}/></label>
        <label>시작월 <input aria-label="시작월" type="month" value={from} onChange={e=>e.target.value && update({from:e.target.value})} className="border border-slate-200 rounded p-2"/></label>
        <label>종료월 <input aria-label="종료월" type="month" value={to} onChange={e=>e.target.value && update({to:e.target.value})} className="border border-slate-200 rounded p-2"/></label>
        <Link className="text-blue-700 underline" to={`/?${linkQuery}`}>종합 대시보드</Link>
      </div>
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-slate-600">
        실측 원천 보유 현황 · QC 승인 전 · 자료가 없는 기간을 관측 중단으로 단정하지 않습니다. 수집률·수신 상태는 수신 이력과 예정 관측건수 확인이 필요합니다.
        {lake && <p className="mt-1">원천 관측시각: {lake.totals.first_clock || '미확정'} ~ {lake.totals.last_clock || '미확정'} · 시간대 미확정 · {lake.totals.held_months}개월 보유<br/>검증본: {lake.snapshot} · {lake.legacy_status || lake.note}</p>}
      </div>
      {loading && <p role="status" className="text-sm text-blue-600">보유 자료 조회 중…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      {/* 6 Top Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <div className="bg-blue-50 p-1.5 rounded-lg"><Building2 className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">보유 관측소</span>
          </div>
          <p className="text-xl xl:text-2xl font-black break-all text-slate-800">{summary.total ?? '—'} <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>운영중 <span className="font-bold text-slate-700">미확정</span></span>
            <span>정지 <span className="font-bold text-slate-700">미확정</span></span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <div className="bg-blue-50 p-1.5 rounded-lg"><Activity className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">수집률</span>
          </div>
          <p className="text-xl xl:text-2xl font-black break-all text-slate-800">미산정 <span className="text-sm font-normal text-slate-500"></span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>수신 이력 검증 전</span>
            <span className="text-emerald-500 font-bold flex items-center gap-0.5">미산정</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-emerald-500 mb-2">
            <div className="bg-emerald-50 p-1.5 rounded-lg"><CheckCircle className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">정상 수신 중</span>
          </div>
          <p className="text-xl xl:text-2xl font-black break-all text-slate-800">미확정 <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>수신 이력 검증 전</span>
            <span className="text-emerald-500 font-bold">미산정</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-amber-500 mb-2">
            <div className="bg-amber-50 p-1.5 rounded-lg"><Clock className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">수신 지연</span>
          </div>
          <p className="text-xl xl:text-2xl font-black break-all text-slate-800">미확정 <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>수신 이력 검증 전</span>
            <span className="text-amber-500 font-bold">미산정</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-red-500 mb-2">
            <div className="bg-red-50 p-1.5 rounded-lg"><AlertTriangle className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">수신 중단</span>
          </div>
          <p className="text-xl xl:text-2xl font-black break-all text-slate-800">미확정 <span className="text-sm font-normal text-slate-500">개소</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>수신 이력 검증 전</span>
            <span className="text-amber-500 font-bold">미산정</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex flex-col justify-between">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <div className="bg-blue-50 p-1.5 rounded-lg"><Database className="w-5 h-5" /></div>
            <span className="text-xs font-bold text-slate-700">보유 원천 행 수</span>
          </div>
          <p className="text-xl xl:text-2xl font-black break-all text-slate-800">{summary.held_rows?.toLocaleString('ko-KR') ?? '—'} <span className="text-sm font-normal text-slate-500">건</span></p>
          <div className="flex justify-between mt-3 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
            <span>원천 보유량</span>
            <span className="text-slate-500 font-bold">선택 기간 합계</span>
          </div>
        </div>
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-5">

        {/* Left Col - Map & Line Chart */}
        <div className="xl:col-span-1 flex flex-col gap-5">
          {/* Map */}
          <div className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 flex flex-col h-[400px]">
            <h3 className="text-sm font-bold text-slate-800 mb-2">관측소 위치 및 상태 지도</h3><p className="text-[10px] text-slate-500 mb-2">기존 PostgreSQL 좌표·관측망·해역 참조 · 지도 {mapMarkers.length}/{summary.total ?? '—'}개소 · {metadataError || '좌표 누락 관측소는 표에서 조회'}</p>
            <div className="flex-1 rounded-lg overflow-hidden border border-slate-200 relative">
              <MapContainer center={[36.5, 127.5]} zoom={6} style={{ height: '100%', width: '100%' }} zoomControl={false}>
                <OSMBaseLayer/>
                {filteredMapMarkers.map((marker, i) => (
                  <Marker key={i} position={[marker.lat, marker.lng]} icon={createCustomIcon(marker.status, marker.name)} eventHandlers={{click:()=>{setSelectedStation(marker.id);setStationSearch('');}}}>
                    <Popup>
                      <div className="text-xs font-bold">{marker.name}</div>
                      <div className="text-[10px] text-slate-500">{marker.sea} | {marker.net} ({marker.id})</div>
                      <div className="text-[10px] font-bold mt-1">수신 상태: {marker.status}</div><Link className="text-blue-700 underline" to={`/profile/${encodeURIComponent(marker.id)}?${linkQuery}`}>실측·근거 상세</Link>
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
              {/* Legend overlay */}
              <div className="absolute top-3 right-3 bg-slate-900/80 backdrop-blur-sm p-2 rounded border border-slate-700 text-[10px] text-slate-300 z-[400]">
                <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-slate-500"></div> 수신 상태 미확정</div>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3 text-xs">


              <button onClick={resetTable} className="text-blue-600 font-medium px-2 py-1.5 hover:bg-blue-50 rounded">전체 목록 보기</button>
            </div>
          </div>

          {/* Line Chart */}
          <div className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 h-[300px] flex flex-col">
            <h3 className="text-sm font-bold text-slate-800 mb-4">월별 보유 원천 행 수 <span className="text-xs font-normal text-slate-500">(선택 기간 · 미등록 월은 공백)</span></h3>
            <div className="flex-1 w-full text-xs">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fill: '#64748B'}} />
                  <YAxis domain={[0, 'auto']} tickFormatter={v => Intl.NumberFormat('ko-KR', {notation:'compact'}).format(v)} axisLine={false} tickLine={false} tick={{fill: '#64748B'}} width={30} />
                  <RechartsTooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Legend iconType="plainline" wrapperStyle={{ fontSize: '11px', top: -10 }} />
                  <Line type="monotone" dataKey="total" name="보유 행 수" stroke="#3B82F6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Middle Col - Table & Progress Bars */}
        <div className="xl:col-span-2 flex flex-col gap-5">
          {/* Table */}
          <div id="observation-table" className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 flex flex-col h-[400px]">
            <div className="flex flex-wrap gap-2 justify-between items-center mb-4">
              <h3 className="text-sm font-bold text-slate-800">관측소별 보유·수신 현황</h3>
              <div className="flex flex-wrap gap-2 text-xs"><input aria-label="관측소 검색" placeholder="관측소명·코드" value={stationSearch} onChange={e=>setStationSearch(e.target.value)} className="border border-slate-200 rounded px-2 py-1 w-32"/>


                <select value={filterStat} onChange={e => setFilterStat(e.target.value)} className="border border-slate-200 rounded px-2 py-1 bg-white outline-none text-slate-600">
                  <option value="전체 상태">전체 상태</option>
                  {uniqueStats.map(stat => <option key={stat as string} value={stat as string}>{stat as string}</option>)}
                </select>
                <button aria-label="표 필터 초기화" onClick={resetTable} className="border border-slate-200 rounded px-2 py-1 text-slate-600 hover:bg-slate-50"><Menu className="w-3.5 h-3.5" /></button>
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              <table className="w-full text-xs text-left">
                <thead className="text-slate-500 bg-slate-50 border-y border-slate-200 sticky top-0">
                  <tr>
                    <th className="py-2.5 px-3 font-medium">관측소명</th>
                    <th className="py-2.5 px-3 font-medium">관측망</th>
                    <th className="py-2.5 px-3 font-medium">해역</th>
                    <th className="py-2.5 px-3 font-medium text-right">수집률</th>
                    <th className="py-2.5 px-3 font-medium text-center">수신 상태</th>
                    <th className="py-2.5 px-3 font-medium text-center">최종 관측시각(시간대 미확정)</th>
                    <th className="py-2.5 px-3 font-medium text-center">지연 시간</th>
                    <th className="py-2.5 px-3 font-medium">보유 자료</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {filteredTableData.map((row, i) => (
                    <tr key={i} onClick={()=>setSelectedStation(row.id)} className={`cursor-pointer transition-colors ${selectedStation===row.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}>
                      <td className="py-2.5 px-3 font-medium text-slate-800"><button aria-pressed={selectedStation===row.id} className="text-blue-700 hover:underline text-left" onClick={()=>setSelectedStation(row.id)}>{row.name}<span className="block text-[10px] text-slate-500">{row.id}</span></button></td>
                      <td className="py-2.5 px-3">{row.net}</td>
                      <td className="py-2.5 px-3">{row.sea}</td>
                      <td className="py-2.5 px-3 text-right">{row.rate}</td>
                      <td className={`py-2.5 px-3 text-center font-bold ${row.statColor}`}>{row.stat}</td>
                      <td className="py-2.5 px-3 text-center">{row.time}</td>
                      <td className="py-2.5 px-3 text-center">{row.delay}</td>
                      <td className="py-2.5 px-3 text-xs text-slate-500">{row.note}</td>
                    </tr>
                  ))}
                  {!filteredTableData.length && <tr><td colSpan={8} className="py-6 text-center text-slate-500">{loading ? '조회 중…' : error ? '자료 조회 실패' : '선택 범위·필터에 보유 자료가 없습니다.'}</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="mt-3 text-center border-t border-slate-100 pt-3">
              <button onClick={resetTable} className="text-xs text-blue-600 font-medium hover:underline">필터 해제 · 전체 {tableData.length}개소 보기 →</button>
            </div>
          </div>

          {/* Bottom Right Layout Split: Progress Bars & Lists */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 h-[300px]">
            {/* Progress Bars */}
            <div className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 flex flex-col">
              <h3 className="text-sm font-bold text-slate-800 mb-4">관측소별 보유 항목 수</h3>
              <p className="text-[10px] text-slate-500 mb-2">원천 항목 코드 {summary.items ?? '—'}종 · 막대는 최대 항목 수 대비 비중이며 수집률이 아닙니다.</p><div className="flex-1 overflow-auto space-y-3.5 text-xs pr-2">
                {typeStatus.map((item, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Link className="w-20 truncate font-medium text-blue-700" to={`/profile/${encodeURIComponent(item.id)}?${linkQuery}`}>{item.name}</Link>
                    <div className="flex-1 bg-slate-100 h-2.5 rounded-full overflow-hidden flex items-center relative">
                      <div className={`h-full ${item.color} rounded-full`} style={{ width: `${item.rate}%` }}></div>

                    </div>
                    <span className={`w-8 text-right font-bold ${item.statColor}`}>{item.stat}</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 text-center border-t border-slate-100 pt-2">
                <Link className="text-xs text-blue-600 font-medium hover:underline" to="/data-lake">원천·항목 검증 현황 보기 →</Link>
              </div>
            </div>

            {/* Notifications & Lists */}
            <div className="flex flex-col gap-5">
              <div className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 flex-1 overflow-hidden flex flex-col">
                <h3 className="text-sm font-bold text-slate-800 mb-3">최근 보유 관측시각</h3>
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
                          <Link className="font-medium text-blue-700" to={`/profile/${encodeURIComponent(item.id)}?${linkQuery}`}>{item.name}</Link>
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
              <div className="bg-white border border-blue-100 rounded-2xl shadow-sm p-4 flex-1 overflow-hidden flex flex-col">
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
                     <div className="text-xs text-slate-400 text-center mt-4">실시간 수신 알림 미연결 · 알림 없음으로 판정하지 않습니다.</div>
                  )}
                </div>
                <div className="mt-2 text-center border-t border-slate-100 pt-2">
                  <Link className="text-[11px] text-blue-600 font-medium hover:underline" to="/alerts">전체 알림 보기 →</Link>
                </div>
              </div>
            </div>
          </div>

        </div>
        <StationQuickView station={tableData.find(r=>r.id===selectedStation)} source={source} from={from} to={to} snapshot={lake?.snapshot}/>
      </div>
    </div>
  );
};

export default Observations;
