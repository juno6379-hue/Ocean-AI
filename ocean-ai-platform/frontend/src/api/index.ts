// 파일 역할: 화면에서 사용하는 백엔드 API 호출 함수를 제공합니다.
import { apiFetch } from './client';
// API 호출을 위한 기본 설정 및 함수들
// 백엔드의 FastAPI 서버(기본 8000포트)와 통신합니다.

import { API_BASE_URL } from './client';

/**
 * 공통 Fetch 함수
 * @param endpoint API 엔드포인트
 * @param options fetch 옵션
 * @returns JSON 파싱된 응답
 */
async function fetchApi(endpoint: string, options?: RequestInit) {
  const response = await apiFetch(`${API_BASE_URL}${endpoint}`, options);
  if (!response.ok) {
    throw new Error(`API 호출 실패: ${response.statusText}`);
  }
  return response.json();
}

/**
 * 대시보드 요약 정보 조회
 */
export async function getDashboardSummary() {
  return fetchApi('/dashboard/summary');
}

/**
 * 최근 이벤트 조회
 */
export async function getRecentEvents() {
  return fetchApi('/events').then(data => data.events);
}

/**
 * 위험 관측소 목록 조회
 */
export async function getRiskStations() {
  return fetchApi('/ai-insights/summary').then(data => data.station_quality_risk);
}

/**
 * 전체 관측소 목록 조회
 */
export async function getStations() {
  return fetchApi('/stations');
}

/**
 * 특정 관측소 프로파일(상세 정보 및 센서 목록) 조회
 * @param stationId 관측소 ID (예: DT_0001)
 */
export async function getStationProfile(stationId: string) {
  return fetchApi(`/stations/${stationId}/profile`);
}

/**
 * 특정 관측소의 최근 관측자료(시계열 데이터) 조회
 * @param stationId 관측소 ID
 */
export async function getObservations(stationId: string) {
  return fetchApi(`/observations?station_id=${stationId}&limit=50`);
}

export async function getDataLakeSummary(lakeName?: string) {
  return fetchApi(`/data-lake/summary${lakeName ? `?lake_name=${encodeURIComponent(lakeName)}` : ''}`);
}
export async function getLongTermInsights(stationId?: string) { return fetchApi(`/ai-insights/long-term${stationId ? `?station_id=${encodeURIComponent(stationId)}` : ''}`); }
