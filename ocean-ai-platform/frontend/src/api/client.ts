// 파일 역할: 서버 요청에 공통 주소·인증 정보·오류 처리를 적용합니다.
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
import axios from 'axios';

let operatorToken = '';
export function setOperatorToken(token: string) { operatorToken = token.trim(); }
export function clearOperatorToken() { operatorToken = ''; }
export function apiFetch(input: RequestInfo | URL, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  if (operatorToken) headers.set('Authorization', `Bearer ${operatorToken}`);
  return fetch(input, { ...init, headers });
}
export const apiClient = axios.create();
apiClient.interceptors.request.use(config => {
  if (operatorToken) config.headers.Authorization = `Bearer ${operatorToken}`;
  return config;
});
