// 파일 역할: 프런트엔드 애플리케이션을 화면에 연결합니다.
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css'; // TailwindCSS가 포함된 글로벌 스타일

/**
 * React 애플리케이션의 메인 진입점입니다.
 * BrowserRouter로 라우팅 컨텍스트를 제공합니다.
 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
