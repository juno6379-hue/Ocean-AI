// 파일 역할: 관측소별 기준정보와 상세 현황을 표시합니다.
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getStationProfile, getObservations } from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, MapPin } from 'lucide-react';

/**
 * 개별 관측소의 품질 프로파일 및 관측자료 시계열 그래프를 보여주는 화면입니다.
 * URL 파라미터로 전달된 관측소 ID를 바탕으로 데이터를 조회합니다.
 */
const StationProfile: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<any>(null);
  const [observations, setObservations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      getStationProfile(id),
      getObservations(id)
    ]).then(([profileData, obsData]) => {
      setProfile(profileData);

      // 최신 데이터가 오른쪽으로 가도록 역순 정렬 후 시간 포맷 조정
      const chartData = obsData.reverse().map((o: any) => ({
        ...o,
        time: new Date(o.timestamp_utc).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }),
        value: o.value_raw === -999.0 ? null : o.value_raw, // 결측치 처리
        isBad: o.value_status === 'BAD'
      }));
      setObservations(chartData);
      setLoading(false);
    }).catch(err => {
      console.error('프로파일 데이터 로드 실패:', err);
      setLoading(false);
    });
  }, [id]);

  if (loading) return <div className="p-10">불러오는 중...</div>;
  if (!profile) return <div className="p-10 text-red-400">관측소 정보를 찾을 수 없습니다.</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <MapPin className="w-6 h-6 text-blue-500" />
          {profile.station.station_name} 관측소 프로파일
        </h2>
        <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm">
          {profile.station.status}
        </span>
      </div>

      {/* 기본 정보 및 센서 정보 영역 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-lg font-bold mb-4">관측소 기본 정보</h3>
          <ul className="space-y-2 text-sm text-slate-300">
            <li><span className="text-slate-500 inline-block w-24">관측소 ID:</span> {profile.station.station_id}</li>
            <li><span className="text-slate-500 inline-block w-24">관측망 유형:</span> {profile.station.network_type}</li>
            <li><span className="text-slate-500 inline-block w-24">해역:</span> {profile.station.sea_area || '정보 없음'}</li>
            <li><span className="text-slate-500 inline-block w-24">위도/경도:</span> {profile.station.latitude || '-'} / {profile.station.longitude || '-'}</li>
          </ul>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 className="text-lg font-bold mb-4">설치 센서 목록</h3>
          <div className="space-y-3">
            {profile.sensors.map((sensor: any) => (
              <div key={sensor.id} className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex justify-between items-center">
                <div>
                  <p className="font-bold text-sm">{sensor.sensor_id}</p>
                  <p className="text-xs text-slate-500">항목: {sensor.variable_code} | 타입: {sensor.sensor_type}</p>
                </div>
                <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded">
                  {sensor.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 시계열 데이터 차트 영역 */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          최근 관측 시계열 데이터 (조위)
        </h3>
        <div className="h-80 w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={observations} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                itemStyle={{ color: '#38bdf8' }}
              />
              <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
              {/* 오류로 판정된 데이터에 붉은색 마킹을 추가하는 것도 좋은 방법입니다 */}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default StationProfile;
