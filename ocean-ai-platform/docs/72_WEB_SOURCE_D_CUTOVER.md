# 수정 소스의 D: 반영 및 로컬 웹 전환

사용자 지시: 루트는 종합 대시보드, 수정 소스를 D: 이전에 반영한다.

- 신규 플랫폼 소스: `D:\AI_Observation\source\ocean-ai-platform`
- 기존 Git 체크아웃/전환 전 소스: `C:\AI_Observation\ocean-ai-platform`
- 기존 납품 소스 보관: `D:\AI_Observation\source\classified\소스코드\03.소스` (수정 대상 아님)
- 계획/파일별 SHA-256/전환 결과: `D:\AI_Observation\metadata\migration\web_source_20261007`

실제 완료 여부는 위 경로의 `status.json`과 `cutover-verification.json`으로 판정한다.
이 문서 작성 시점에는 복사·전환 실행 전이며 확인 없이 완료로 읽으면 안 된다.

## 범위

현재 수정된 frontend/backend/docs, 로컬 설정, 기존 설치된 frontend/node_modules를
새 대상에 복사한다. 파일별 원본/대상 SHA-256과 원본 변경 여부를 확인한다.
이미 존재하는 다른 내용은 덮어쓰지 않고 충돌로 중단한다.
산출 dist는 D:에서 다시 빌드한다. 테스트 작업파일·원장·로그·DB·벡터·원천·레이크는
소스 복사에서 제외하여 실행 중인 작업과 대용량 이전을 중복하지 않는다.

기존 문서·벡터 배치는 현재 데이터 위치를 계속 사용한다.
`OCEAN_APP_DATA_DIR`/`DOCUMENT_PIPELINE_DIR`로 C:의 활성 문서 계약·원장을 명시하고,
Chroma 서버 8001을 공유한다. 비어 있는 D:에 새 벡터 컬렉션을 초기화하지 않는다.
Parquet/검증본은 기존 D: 설정을 사용한다. PostgreSQL 연결정보는 `.env`에서 그대로 유지한다.

`start_web_local.ps1 -Service Backend`는 기존 문서 데이터 위치를 명시한 채 백엔드를 실행하고,
`-Service Frontend`는 해당 스크립트가 있는 프로젝트의 frontend를 실행한다.
기본 포트는 8000/5173. 두 명령은 각각 별도 프로세스에서 실행한다.
기존 서버가 있으면 중복 실행하지 않고 PID/시작시각/경로를 확인한 후 전환한다.

## 남기는 경계

웹 소스/서버 전환과 전체 원천·레이크·Git·문서 런타임의 최종 이전은 별개이다.
Git 원장은 C:\AI_Observation에 보존하며 소스 복사본이 별도 Git 저장소가 됐다고 주장하지 않는다.
현재 실행 중인 C: 원장 참조가 남아 있어 C: 원본을 삭제하지 않는다.
후속 변경은 D: 플랫폼 소스에 적용하고, Git에 반영할 때 변경 목록·해시를 대조하여
기존 체크아웃의 무관한 사용자 변경을 함께 커밋하지 않는다.

문서/벡터 런타임의 쓰기를 종료·정산하고 별도 이전을 검증하기 전에는 C: 의존성 제거가 완료되지 않는다.
웹 전환 실패 시 보존한 C: 서버를 재가동할 수 있다. 기존 서버 외 데이터 worker를 중단하지 않는다.
