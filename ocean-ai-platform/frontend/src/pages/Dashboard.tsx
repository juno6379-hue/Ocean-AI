import StationClassifications, { DatasetSourceSelect } from '../components/StationClassifications';
import OSMBaseLayer from '../components/OSMBaseLayer';
import EvidenceMonitor from '../components/EvidenceMonitor';
// 파일 역할: 관측 및 품질관리 통합 현황을 표시합니다.
import { apiFetch } from '../api/client';
import { API_BASE_URL } from '../api/client';
import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { 
  Building2, Activity, CheckCircle, Bug, AlertTriangle, FileText, 
  ChevronRight
} from 'lucide-react';
import { MapContainer, Marker, Popup } from 'react-leaflet';
import { FACILITY_TYPES, FacilitySymbol, facilityMapIcon } from '../components/FacilityMapSymbol';
import 'leaflet/dist/leaflet.css';
import { 
  LineChart, Line, PieChart, Pie, Cell, 
  XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer
} from 'recharts';

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [monitor, setMonitor] = useState<any>(null);
  const [monitorError, setMonitorError] = useState('');
  const [summaryData, setSummaryData] = useState<any>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [lastSynced, setLastSynced] = useState<Date | null>(null);
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const source = search.get('source') || 'GD_OBS_ST_MONTHLY';
  const from = search.get('from') || (source === 'HISTORICAL_RECONCILED' ? '2011-01' : '2023-01');
  const to = search.get('to') || (source === 'HISTORICAL_RECONCILED' ? '2021-12' : '2026-07');
  const query = new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source, from_month: from, to_month: to}).toString();
  const linkQuery = new URLSearchParams({network:search.get('network')||'',sea:search.get('sea')||'',source, from, to}).toString();
  const [stationFilter, setStationFilter] = useState('');
  const [itemFilter, setItemFilter] = useState('');
  const [facilityCounts, setFacilityCounts] = useState<Record<string, number> | null>(null);
  const network = search.get('network') || '';
  const chooseFacility = (value: string) => { setStationFilter(''); setItemFilter(''); update({network:value, station:'', item:''}); };
  const [revision, setRevision] = useState(0);
  const [metadataError, setMetadataError] = useState('');
  const [reportError, setReportError] = useState('');
  const [reportCount, setReportCount] = useState<number | null>(null);
  const reportTypes: Record<string,string> = {weekly:'주간', monthly:'월간', anomaly:'이상', special:'특별', daily:'일일', quality:'품질', technical:'기술', publication:'간행물'};
  const reportStates: Record<string,string> = {DRAFT:'초안', REVIEW:'검토 대기', APPROVED:'승인', PUBLISHED:'게시', REJECTED:'반려'};
  const update = (values: Record<string, string>) => setSearch({...Object.fromEntries(search), ...values});

  // DB Fetched Data
  const [modelData] = useState<any[]>([]);
  const [loadError, setLoadError] = useState('');
  const mlopsAlerts = (monitor?.events || []).map((e:any) => ({text:`${e.station_name} · ${e.item_codes.join(', ')}`,state:'미승인',stateColor:'text-amber-700 border-amber-200',desc:e.claim,time:e.period_start}));
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

  // Preserve the original dashboard layout; only its data contract changes.
  // Observation counts come exclusively from the shared Parquet catalog.
  // SQL coordinates are optional reference metadata, never evidence of QC or operation.
  useEffect(() => {
    const control = new AbortController();
    setMonitor(null); setMonitorError(''); setStationFilter(''); setItemFilter(''); setFacilityCounts(null);
    setLoading(true); setLoadError(''); setMetadataError(''); setSummaryData(null); setLastSynced(null);
    const read = async (path: string) => {
      const response = await apiFetch(`${API_BASE_URL}${path}`, {signal: control.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    };
    if (from > to) { setLoadError('시작월은 종료월보다 늦을 수 없습니다.'); setLoading(false); return () => control.abort(); }
    Promise.all([
      read(`/lake/summary?${query}`),
      read(`/lake/monitoring?${query}`).catch(() => { if(!control.signal.aborted)setMonitorError('문서·품질 집계 조회 실패'); return null; }),
      read('/stations?limit=10000').catch(() => { if (!control.signal.aborted) setMetadataError('시설 분류·지도 좌표 조회 실패'); return null; }),
      network ? read(`/lake/summary?${new URLSearchParams({...Object.fromEntries(new URLSearchParams(query)),network:''})}`).catch(() => null) : Promise.resolve(null),
    ]).then(([lake, monitoring, metadata, allFacilities]) => {
      if (control.signal.aborted) return;
      if(monitoring?.snapshot === lake.snapshot) setMonitor(monitoring);
      else if(monitoring) setMonitorError('검증본 전환 중 · 새로고침 필요');
      const byCode = new Map<string, any[]>();
      for (const row of metadata || []) byCode.set(row.station_id, [...(byCode.get(row.station_id) || []), row]);
      const baseline = network ? allFacilities : lake;
      if (metadata && baseline?.snapshot === lake.snapshot) {
        const counts: Record<string, number> = {'': baseline.stations.length};
        for (const r of baseline.stations) {
          const refs = byCode.get(r.station_code) || [];
          const key = refs.length === 0 ? '__UNREGISTERED__' : refs.length === 1 && refs[0].network_type ? refs[0].network_type : '__UNASSIGNED__';
          counts[key] = (counts[key] || 0) + 1;
        }
        setFacilityCounts(counts);
      }
      const stations = lake.stations.map((row: any) => {
        const candidates = byCode.get(row.station_code) || [];
        // Ambiguous code matches are not assigned coordinates or a replacement name.
        const ref = candidates.length === 1 ? candidates[0] : null;
        const coordinatesValid = Number.isFinite(ref?.latitude) && Number.isFinite(ref?.longitude)
          && Math.abs(ref.latitude) <= 90 && Math.abs(ref.longitude) <= 180;
        return {...row, station_id: row.station_code, name: row.station_name || row.station_code,
          latitude: coordinatesValid ? ref.latitude : null, longitude: coordinatesValid ? ref.longitude : null,
          facility_type: ref?.network_type || null,
          network_type: !metadata ? '분류 조회 실패' : candidates.length > 1 ? '분류 대응 미확정' : ref ? (ref.network_type || 'DB 분류값 없음') : 'DB 기준정보 미등록', sea_area: ref ? (ref.sea_area || 'DB 해역값 없음') : 'DB 기준정보 미등록',
          qc: '미승인', qcColor: 'bg-slate-50 text-slate-600 border-slate-200',
          val: row.held_rows.toLocaleString('ko-KR'),
          diff: row.last_clock || '미확정', diffColor: 'text-slate-500'};
      });
      setSummaryData({...lake, total_stations: lake.totals.stations, station_summary: stations,
        qc_pie_data: lake.approval_status === 'UNAPPROVED' && lake.totals.held_rows > 0
          ? [{name: 'QC 승인 전 원천', value: lake.totals.held_rows, color: '#94A3B8'}] : []});
      setLastSynced(new Date());
    }).catch(error => { if (!control.signal.aborted) setLoadError(`실측자료 조회 실패: ${error.message}`); })
      .finally(() => { if (!control.signal.aborted) setLoading(false); });
    return () => control.abort();
  }, [query, revision]);

  useEffect(() => {
    const control = new AbortController();
    setReportError(''); setReportCount(null); setRecentReports([]);
    apiFetch(`${API_BASE_URL}/reports`, {signal: control.signal}).then(async response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }).then(data => {
      if (control.signal.aborted) return;
      setReportCount(data.reports.length);
      setRecentReports(data.reports.slice(0, 4).map((r: any) => ({id:r.report_id, title:r.report_title || '제목 미등록', type:reportTypes[r.report_type?.toLowerCase()] || r.report_type || '유형 미등록', status:reportStates[r.status] || r.status || '상태 미확정', time:r.created_at ? r.created_at.replace('T',' ').slice(0,16) : '생성일 미등록'})));
    }).catch(() => { if (!control.signal.aborted) setReportError('보고서 등록부 조회 실패'); });
    return () => control.abort();
  }, [revision]);

  const itemOptions = Array.from(new Set<string>((monitor?.channels || [])
    .filter((c: any) => !stationFilter || c.station_code === stationFilter).map((c: any) => c.item_code))).sort();
  const displayedStations = (summaryData?.station_summary || []).filter((r: any) =>
    (!stationFilter || r.station_id === stationFilter) && (!itemFilter || monitor?.channels?.some((c: any) => c.station_code === r.station_id && c.item_code === itemFilter)))
    .map((r: any) => itemFilter ? {...r, val: monitor.channels.filter((c: any) => c.station_code === r.station_id && c.item_code === itemFilter).reduce((n: number, c: any) => n + c.held_rows, 0).toLocaleString('ko-KR'), diff: '항목별 시각 미조회'} : r);
  const collectionReason = monitorError ? '산정 근거 조회 실패' : !monitor ? '산정 근거 조회 중' : monitor.observations?.collection_reason || '수집률 산정 API 미연결';
  const selectStation = (value: string) => { setStationFilter(value); setItemFilter(''); };
  const detailQuery = new URLSearchParams({network,sea:search.get('sea')||'',source,from,to,station:stationFilter,item:itemFilter}).toString();
  const mappedCount = displayedStations.filter((r: any) => r.latitude != null && r.longitude != null).length;

  return (
    <div className="p-4 md:p-6 space-y-5 bg-gradient-to-br from-blue-50/60 via-white to-indigo-50/40 min-h-full">
      {loadError && <p role="alert" className="text-red-700">{loadError}</p>}
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs text-slate-700">
        월별 실측 원천 · {from} ~ {to} · QC 승인 전 · 수집률은 예정 관측건수 확인 후 산정합니다.
        <Link className="ml-2 font-bold underline" to={`/data-lake?${linkQuery}`}>원천 검증 현황</Link>
        {summaryData && <p className="mt-1">보유 {summaryData.totals.held_rows.toLocaleString('ko-KR')}행 · {summaryData.totals.held_months}개월 · 원천 시각 {summaryData.totals.first_clock || '미확정'} ~ {summaryData.totals.last_clock || '미확정'} (시간대 미확정)<br/>검증본: {summaryData.snapshot} · {summaryData.legacy_status || summaryData.note}</p>}
      </div>
      {loading && <p role="status" className="text-sm text-blue-600">실측자료를 조회하고 있습니다…</p>}
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-3xl font-extrabold text-slate-900">종합 대시보드</h2>
          <p className="text-sm text-slate-500 mt-1">해양관측 전체 현황을 한눈에 확인하세요.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="text-slate-500 hidden sm:inline-block font-mono tracking-tight">{formatTime(currentTime)}</span>
          <div className="flex flex-wrap gap-2">
            <DatasetSourceSelect source={source}/>
            <input aria-label="시작월" type="month" value={from} onChange={e => e.target.value && update({from:e.target.value})} className="border border-slate-200 rounded px-2 py-1.5"/>
            <input aria-label="종료월" type="month" value={to} onChange={e => e.target.value && update({to:e.target.value})} className="border border-slate-200 rounded px-2 py-1.5"/>
            <button onClick={() => setRevision(r => r + 1)} className="border border-slate-200 bg-white rounded px-2 py-1.5">새로고침</button>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 text-slate-700 font-medium rounded-md shadow-sm">
            <div className={`w-2 h-2 rounded-full ${lastSynced ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`}></div>
            <span className="text-xs">{lastSynced ? '실측 조회 연결' : '연결 대기'}</span>
          </div>
        </div>
      </div>

    <StationClassifications/>
      {/* Top 6 Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {[
          { title: '보유 관측소', val: summaryData?.total_stations ?? '—', unit: '개소', icon: Building2, color: 'text-blue-600', bg: 'bg-blue-50', sub1: '보유 기준', sub1V: '', sub2: '운영 상태', sub2V: '미확정' },
          { title: '수집률', val: summaryData?.data_collection_rate ?? '미산정', unit: '', icon: Activity, color: 'text-blue-600', bg: 'bg-blue-50', diffText: '예정 수집건수 필요', diffVal: '-', diffColor: 'text-emerald-500' },
          { title: 'QC 정상 비율', val: '미산정', unit: '', icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-50', diffText: '승인 QC 집계 필요', diffVal: '-', diffColor: 'text-emerald-500' },
          { title: 'BAD 비율', val: '미산정', unit: '', icon: Bug, color: 'text-red-500', bg: 'bg-red-50', diffText: '승인 QC 집계 필요', diffVal: '-', diffColor: 'text-red-500' },
          { title: '문서 검토 후보', val: monitor?.events.length ?? '—', unit: '건', icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50', diffText: '기간 대응 · 원인 미승인', diffVal: '', diffColor: 'text-slate-600' },
          { title: 'AI 분석 리포트', val: reportCount ?? '—', unit: '건', icon: FileText, color: 'text-purple-500', bg: 'bg-purple-50', diffText: '전체 등록부 · 초안 포함', diffVal: '', diffColor: 'text-slate-600' },
        ].map((card, i) => (
          <div key={i} className="bg-white border border-blue-100 p-4 rounded-2xl shadow-sm flex flex-col justify-between">
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
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[520px] lg:h-[540px]">
          <div className="flex items-center justify-between gap-2 mb-2"><h3 className="text-sm font-bold text-slate-800">관측소 현황 지도</h3><button onClick={() => chooseFacility('')} className="text-xs text-blue-700 rounded focus-visible:ring-2 focus-visible:ring-blue-500">전체 해제</button></div>
          <div role="group" aria-label="시설 유형 선택 및 기호 범례" className="grid grid-cols-2 xl:grid-cols-3 gap-1 mb-2">
            {[{value:'', label:'전체'}, ...FACILITY_TYPES].map(type => <button key={type.value} type="button" aria-pressed={network === type.value} onClick={() => chooseFacility(type.value)} className={`flex items-center gap-1.5 rounded-lg border px-2 py-2 text-[11px] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${network === type.value ? 'border-blue-300 bg-blue-50 text-blue-800 font-semibold' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
              {type.value ? <FacilitySymbol type={type.value} className="w-4 h-4 shrink-0"/> : <Building2 className="w-4 h-4 shrink-0"/>}<span className="flex-1">{type.label}</span><span className="tabular-nums">{facilityCounts ? facilityCounts[type.value] || 0 : '—'}</span>
            </button>)}
          </div>
          <div className="text-[10px] text-slate-600 mb-2 space-y-1">
            <p>범례 수: 선택 원천·기간·해역의 자료 보유 시설 · 운영 시설 수 아님</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-slate-500 mr-1"/>회색: 운영 미확정 / QC 미승인 · 기호: 시설 유형</p>
            {!!facilityCounts?.__UNREGISTERED__ && <button aria-pressed={network === '__UNREGISTERED__'} onClick={() => chooseFacility('__UNREGISTERED__')} className="underline text-blue-700">기준정보 미등록 {facilityCounts.__UNREGISTERED__}개소 포함</button>}
            {!!facilityCounts?.__UNASSIGNED__ && <p>분류 미지정·대응 미확정 {facilityCounts.__UNASSIGNED__}개소 · 전체에서 확인</p>}
            <p aria-live="polite">현재 표 {displayedStations.length}개소 · 지도 {mappedCount}개소 · 좌표 없는 시설도 표에 표시</p>
            {metadataError && <p role="alert" className="text-red-700">{metadataError}</p>}
            {!loading && !loadError && displayedStations.length === 0 && <p>선택 원천·기간에 보유 자료 없음 · 운영 시설 0개를 뜻하지 않습니다.</p>}
          </div>
          <div className="flex-1 rounded-lg overflow-hidden border border-slate-200 relative z-0">
            <MapContainer center={[36.5, 127.5]} zoom={6} style={{ height: '100%', width: '100%', background: '#F8FAFC' }} zoomControl={false}>
              <OSMBaseLayer/>
              {displayedStations.filter((station: any) => station.latitude != null && station.longitude != null).map((station: any) => (
                <Marker
                  key={station.station_id}
                  position={[station.latitude, station.longitude]}
                  icon={facilityMapIcon(station.facility_type, stationFilter === station.station_id)}
                  title={`${station.name} · ${station.network_type} · 운영 미확정 / QC 미승인`}
                  alt={`${station.name} 시설 선택`}
                  eventHandlers={{click: () => selectStation(station.station_id)}}
                >
                  <Popup>
                    <strong>{station.name}</strong><br />
                    해역: {station.sea_area || '미상'}<br />
                    시설 유형: {station.network_type} (기준정보)<br />운영 미확정 · QC 미승인<br/>
                    관측소 코드: {station.station_id}<br/><Link className="underline" to={`/profile/${encodeURIComponent(station.station_id)}?${linkQuery}`}>실측·근거 상세</Link>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
          <button onClick={() => navigate(`/observations?${detailQuery}`)} className="w-full text-xs text-blue-600 font-medium hover:underline mt-3 flex justify-center items-center gap-1">전체 관측소 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Table */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[520px] lg:h-[540px]">
          <h3 className="text-sm font-bold text-slate-800 mb-3">해양 관측자료 요약</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 gap-2 mb-2">
            <label className="text-[10px] text-slate-500">시설 유형<select value={network} onChange={e => chooseFacility(e.target.value)} className="block w-full border border-slate-200 rounded-lg p-2 mt-1 text-xs text-slate-700"><option value="">전체 시설 유형</option>{FACILITY_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}<option value="__UNREGISTERED__">기준정보 미등록</option></select></label>
            <label className="text-[10px] text-slate-500">관측소<select value={stationFilter} onChange={e => selectStation(e.target.value)} className="block w-full border border-slate-200 rounded-lg p-2 mt-1 text-xs text-slate-700"><option value="">전체 관측소</option>{(summaryData?.station_summary||[]).map((s:any)=><option key={s.station_id} value={s.station_id}>{s.name} ({s.station_id})</option>)}</select></label>
            <label className="text-[10px] text-slate-500">관측 항목<select disabled={!monitor?.observation_metrics_available} value={itemFilter} onChange={e => setItemFilter(e.target.value)} className="block w-full border border-slate-200 rounded-lg p-2 mt-1 text-xs text-slate-700 disabled:bg-slate-50"><option value="">{monitor?.observation_metrics_available ? '전체 항목' : '항목별 집계 미조회'}</option>{itemOptions.map(item => <option key={item} value={item}>{item}</option>)}</select></label>
            <button onClick={() => {setStationFilter(''); setItemFilter('');}} className="self-end p-2 text-xs text-blue-700 rounded-lg border border-blue-100 hover:bg-blue-50">관측소·항목 해제</button>
          </div>
          <p className="text-[10px] text-slate-500 mb-2">지도·표에 동일 적용 · 상단 KPI와 QC 집계는 시설 유형·해역 전체</p>
          <details className="text-[11px] text-slate-600 mb-2 rounded-lg bg-slate-50 p-2"><summary className="cursor-pointer font-medium">수집률 미산정 사유</summary><p className="mt-1">{collectionReason}. 보유 행 수는 중복 제거된 관측 건수가 아니므로 수집률의 분자로 사용하지 않습니다.</p><Link className="underline text-blue-700" to={`/data-lake?${detailQuery}`}>월별 원천 검증 보기</Link></details>
          <div className="flex-1 overflow-auto">
            <table className="w-full text-xs text-left min-w-[300px]">
              <thead className="text-slate-500 bg-slate-50 border-b border-slate-200 sticky top-0">
                <tr>
                  <th className="py-2.5 px-2 font-medium">관측소</th>
                  <th className="py-2.5 px-2 font-medium">보유 행 수</th>
                  <th className="py-2.5 px-2 font-medium">수집률</th>
                  <th className="py-2.5 px-2 font-medium">QC 상태</th>
                  <th className="py-2.5 px-2 font-medium text-right">최종 관측시각</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {displayedStations.map((row: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-2"><button onClick={() => selectStation(row.station_id)} className="text-blue-700 hover:underline text-left">{row.name}</button><Link aria-label={`${row.name} 상세 보기`} className="block text-blue-700 hover:underline" to={`/profile/${encodeURIComponent(row.station_id)}?${linkQuery}`}><span className="block text-[10px] text-slate-500">{row.station_id} · 상세</span></Link></td>
                    <td className="py-2.5 px-2 font-bold">{row.val}</td>
                    <td className="py-2.5 px-2" title={collectionReason}>근거 필요</td>
                    <td className="py-2.5 px-2"><span className={`px-2 py-0.5 border rounded-full text-[10px] font-bold ${row.qcColor}`}>{row.qc}</span></td>
                    <td className={`py-2.5 px-2 text-right font-medium ${row.diffColor}`}>{row.diff}</td>
                  </tr>
                ))}
                {(displayedStations.length === 0) && (
                   <tr><td colSpan={5} className="text-center py-4 text-slate-400">{loading ? '조회 중…' : loadError ? '자료 조회 실패' : '선택 범위에 보유 자료가 없습니다.'}</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <button onClick={() => navigate(`/observations?${detailQuery}`)} className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-2 border-t border-slate-100">전체 관측 데이터 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Donut Chart */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col h-[520px] lg:h-[540px]">
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
                <p className="text-[10px] text-slate-500 font-medium">미승인 원천</p>
                <p className="text-xl font-black text-slate-800">
                  {summaryData?.qc_pie_data?.reduce((acc: number, cur: any) => acc + cur.value, 0).toLocaleString() ?? '—'}
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
          <button onClick={() => navigate('/data-lake')} className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-3 border-t border-slate-100">품질 현황 상세 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Alerts */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[260px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-slate-800">문서 기반 검토 사항</h3>
            <span className="bg-slate-100 text-slate-600 text-[10px] px-2 py-0.5 rounded-full font-bold">{monitor?.events.length ?? '—'}건</span>
          </div>
          <div className="flex-1 overflow-auto space-y-2.5 pr-1">
            <p className="text-xs text-slate-500 p-3">보고서 기간과 보유 관측자료가 대응하는 후보입니다. 원인·QC 승인은 별도입니다.</p>
            {mlopsAlerts.map((alert:any, i:number) => (
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
          <button onClick={() => navigate(`/ai-insights?${linkQuery}`)} className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-3 border-t border-slate-100">문서·관측 근거 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Reports */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[260px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2"><FileText className="w-4 h-4 text-purple-600" /> 최근 AI 분석 리포트</h3>
          </div>
          <div className="flex-1 overflow-auto space-y-2.5 pr-1">
            <p className="text-xs text-slate-500">전체 보고서 등록부 · 선택 관측기간과 별도</p>
            {reportError && <p role="alert" className="text-xs text-red-700">{reportError}</p>}
            {reportCount === null && !reportError && <p role="status" className="text-xs text-slate-500 p-3">보고서 등록부 조회 중…</p>}
            {reportCount === 0 && <p className="text-xs text-slate-500 p-3">등록된 AI 보고서가 없습니다.</p>}
            {recentReports.map(report => (
              <Link key={report.id} to={`/reports?${linkQuery}&report=${encodeURIComponent(report.id)}`} className="block p-2.5 rounded-lg border border-slate-100 hover:border-blue-200 hover:bg-blue-50/40 focus-visible:ring-2 focus-visible:ring-blue-500">
                <div className="flex items-center gap-2"><span className="shrink-0 px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] font-semibold">{report.type}</span><span className="text-xs font-medium text-slate-800 truncate">{report.title}</span></div>
                <div className="flex justify-between mt-1.5 text-[10px] text-slate-500"><span>{report.status}</span><span>생성 {report.time}</span></div>
              </Link>
            ))}
          </div>
          <button onClick={() => navigate(`/reports?${linkQuery}`)} className="w-full text-xs text-blue-600 font-medium hover:underline mt-2 flex justify-center items-center gap-1 pt-3 border-t border-slate-100">전체 리포트 보기 <ChevronRight className="w-3 h-3"/></button>
        </div>

        {/* Model Performance */}
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 h-[260px] flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-sm font-bold text-slate-800">모델 성능 요약</h3>
            <select disabled className="bg-white border border-slate-200 text-xs px-2 py-1.5 rounded text-slate-600 outline-none">
              <option>승인 평가 결과 미등록</option>
            </select>
          </div>
          <div className="flex flex-col sm:flex-row gap-4 mb-2 flex-1">
            <div className="flex flex-row sm:flex-col justify-between sm:justify-start gap-4 sm:w-1/3">
              <div>
                <p className="text-[10px] text-slate-500 font-medium">RMSE (평균)</p>
                <p className="text-2xl font-black text-slate-800">미평가</p>
                <p className="text-[10px] font-bold text-emerald-500">검증 데이터셋 평가 후 표시</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 font-medium">F1 Score (평균)</p>
                <p className="text-2xl font-black text-slate-800">미평가</p>
                <p className="text-[10px] font-bold text-emerald-500">검토 라벨 평가 후 표시</p>
              </div>
            </div>
            <div className="flex-1 h-32 sm:h-full relative">
              {!modelData.length && <p className="absolute inset-0 z-10 flex items-center justify-center bg-white text-xs text-slate-500">승인 모델 성능 데이터 없음</p>}
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
          <button onClick={() => navigate(`/mlops?${linkQuery}`)} className="w-full text-xs text-blue-600 font-medium hover:underline mt-auto pt-3 flex justify-center items-center gap-1 border-t border-slate-100">모델 관리 (MLOps) <ChevronRight className="w-3 h-3"/></button>
        </div>
      </div>
      {monitorError && <p role="alert" className="text-sm text-red-700">{monitorError}</p>}
      <EvidenceMonitor monitor={monitor} from={from} to={to}/>
    </div>
  );
};

export default Dashboard;
