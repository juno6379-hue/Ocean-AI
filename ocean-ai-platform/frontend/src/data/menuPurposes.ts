/** Product guidance, not an account authorization policy. */
export type MenuPurpose = { name: string; purpose: string; role: string; input: string;
  action: string; output: string; pending: string; next: string[]; basis: 'daily'|'quality'|'product' };
export const menuPurposes: Record<string, MenuPurpose> = {
  '/': { name:'종합 대시보드', purpose:'관측망의 자료와 점검 근거를 모아 확인 대상을 찾습니다.', role:'모니터링·총괄 담당 참고',
    input:'원천·기간·관측망·해역과 일일보고 색인', action:'지도·표와 보고서 요약 조회', output:'보유 현황과 상세 확인 대상',
    pending:'수집률 분모·당일 제출상태는 미확정입니다. 대조기 특별점검·조위편차·운영총량의 통합 요약은 아직 미연결입니다.', next:['/observations','/reports','/qc'], basis:'daily' },
  '/observations': { name:'관측 현황', purpose:'시설·항목·기간별 실제 보유자료와 공백을 확인합니다.', role:'모니터링·자료관리 담당 참고',
    input:'선택 원천·기간, 관측소와 항목', action:'지도·표 선택 후 실제 값·계보 조회', output:'보유량·표본값·연결 조건',
    pending:'수집률은 관측주기·유효기간·제외정책에 따른 이론건수 확인이 필요합니다. 보유량으로 대체하지 않습니다.', next:['/qc','/equipment'], basis:'quality' },
  '/qc': { name:'품질 현황 (QC)', purpose:'원천 QC와 관측자료를 문서·장비 근거와 대조합니다.', role:'자료관리 담당 참고',
    input:'관측자료·원천 QC·규칙·단위·기간 근거', action:'원천 표기 분포·결측·사건 근거 조회', output:'검토 근거와 미확정 조건',
    pending:'가이드 전 항목·HF 재검사와 Label 승격은 미완료입니다. 조위편차는 관측−예측의 단위·시각·기준면 대응 확인 후 검토해야 합니다.', next:['/equipment','/alerts'], basis:'quality' },
  '/ai-insights': { name:'AI 분석 인사이트', purpose:'관측 패턴과 문서 사건의 관련 근거를 분석합니다.', role:'자료 분석 담당 활용 제안',
    input:'선택 자료·기간과 문서 사건 후보', action:'추이·사건 지도·원문 인용 확인', output:'추가 검토할 후보와 연결 근거',
    pending:'검증된 AI 원인·신뢰도·전 항목 예측 결과는 아직 제공하지 않습니다.', next:['/qc','/reports'], basis:'product' },
  '/equipment': { name:'장비 & 운영 관리', purpose:'시설·장비 이력과 점검·조치 기록을 대조합니다.', role:'시설관리 담당 참고',
    input:'설치·교체·점검 문서와 자료 보유 관측소', action:'설치 주장·정비·날짜 및 일련번호 후보 조회', output:'장비·사용기간·충돌의 확인 근거',
    pending:'점검 지시·작업 완료와 센서 유효기간 승인은 미연결입니다. 총량산정은 기준일 운영·신설·폐지·배치·계획 대조가 필요하며 등록 코드 수와 다릅니다.', next:['/observations','/reports'], basis:'daily' },
  '/service-monitoring': { name:'서비스 모니터링', purpose:'자료 품질과 구분하여 시스템 실행 상태를 확인합니다.', role:'정보시스템 운영 담당 활용 제안',
    input:'연결된 서비스 상태·실행 기록', action:'조회 결과와 확인 시각 검토', output:'시스템 추가 점검 대상',
    pending:'모든 API·배치·DB·검색의 실시간 감시와 자동 복구는 아직 통합되지 않았습니다.', next:['/system'], basis:'product' },
  '/reports': { name:'보고서 & 문서', purpose:'업무 보고와 판단에 사용한 원문 근거를 확인합니다.', role:'보고 작성·검토 담당 참고',
    input:'보고서 등록부의 요약·대상 기간·생성일·검토 상태', action:'목록·요약 조회와 초안 검토 전환, 권한에 따른 승인·반려 요청', output:'보고서 상태와 서버 검토 기록',
    pending:'원문 파일 미리보기·AI 보고서 생성·양식은 미연결입니다. 일일보고 색인은 제출률이 아니며 대조기 보고 대응은 미검증입니다. 승인과 게시는 별도입니다.', next:['/equipment','/alerts'], basis:'daily' },
  '/mlops': { name:'모델 관리 (MLOps)', purpose:'후보의 평가·승인·배포 준비 근거를 구분해 확인합니다.', role:'모델·자료 검토 담당 활용 제안',
    input:'모델·데이터셋 버전, 기록된 평가와 승인 근거', action:'전체 등록부와 모델별 배포 차단 사유 조회', output:'준비도 검토 결과와 누락 근거',
    pending:'학습 worker·배포·롤백 실증과 가이드 전체 항목/HF 후보 비교는 미완료입니다.', next:['/data-lake','/ai-insights'], basis:'product' },
  '/data-lake': { name:'Data Lake & AI 계획', purpose:'원천에서 학습·평가 자료로 이어지는 계보를 확인합니다.', role:'자료·모델 검토 담당 활용 제안',
    input:'원천·표준자료·manifest·문서 연결과 단계 상태', action:'자료 보유·변환·연결 근거와 미확정 조건 조회', output:'검토 범위와 다음 단계의 선행조건',
    pending:'자동 후보는 승인 Label·Dataset 멤버십이 아닙니다. 승인 학습셋 생성 완료를 뜻하지 않습니다.', next:['/qc','/mlops'], basis:'product' },
  '/forecasting': { name:'조위 예측 기준선', purpose:'마지막 관측값을 유지하는 현재 조위 기준선을 확인합니다.', role:'예측 평가 담당 활용 제안',
    input:'관측소와 연결된 조위 관측값', action:'현재 구현된 기준선 예측 요청·결과 확인', output:'관측값 유지 기준선 응답',
    pending:'학습 AI·범용 항목 예측은 미완료입니다. 이 기준선은 대조기 일정이나 조위편차 검토용 예측조위를 대신하지 않습니다.', next:['/mlops','/observations'], basis:'product' },
  '/alerts': { name:'알림 & 이슈', purpose:'등록된 검토 대상을 확인하고 승인·반려 기록을 남깁니다.', role:'권한을 부여받은 검토자 활용',
    input:'기존 승인 API에 등록된 대기 대상', action:'근거 확인 후 권한에 따른 승인·반려 요청', output:'대상별 검토 상태와 서버 승인 기록',
    pending:'전체 장애의 접수·담당 배정·조치·종결 및 재발 추적은 아직 통합되지 않았습니다.', next:['/qc','/reports'], basis:'product' },
  '/system': { name:'시스템 관리', purpose:'연결된 연동 시험과 실행 결과를 확인합니다.', role:'정보시스템 운영 담당 활용 제안',
    input:'연동 시험 요청과 저장된 결과', action:'구현된 자동시험 요청·결과 확인', output:'연동 시험 결과와 추가 확인 사항',
    pending:'기존 E2E 시나리오는 합성 예시를 포함해 실자료 검증 완료를 뜻하지 않습니다. 운영 데이터와 격리 검증이 필요합니다.', next:['/service-monitoring'], basis:'product' },
};
export function menuPurposeFor(path: string): MenuPurpose | undefined {
  if(path==='/copilot') return menuPurposes['/qc'];
  if(path.startsWith('/profile/')) return {...menuPurposes['/observations'], name:'관측소 상세',
    action:'선택 관측소에 연결된 상세 자료 조회', pending:'개별 필터와 표본 범위를 확인하세요. 공통 기간이 모든 상세 API에 적용되는 것은 아닙니다.'};
  return menuPurposes[path];
}
