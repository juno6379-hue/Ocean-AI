# 상세 구현과 날짜별 실행 기록

이 폴더에는 설계, 특정 날짜의 배치·검증 결과와 구현 계약이 함께 보존되어 있다. **현재 운영 상태·설치·API는 저장소 루트의 [현행 문서 안내](../../docs/README.md)와 01~26 문서를 기준으로 확인한다.** 과거 기록에 있는 완료율, 모델 지표, 파일 수, PID, C/D 경로는 그 검증 시점의 근거다.

- [83: 12종 QC 엔진](83_QC_RULE_ENGINE.md): 실제 가이드 catalog·규칙별 조건·미평가·계보 검증.
- [84: Fusion과 승인 workflow](84_EVIDENCE_FUSION_WORKFLOW.md): 5종 근거 score와 PostgreSQL stop/resume·무결성·멱등성.
- [82: 승인 원천 계약과 모델 실행 연결](82_SOURCE_CONTRACT_AND_MODEL_EXECUTION_RELEASE.md): 현행 source 판정, v2 snapshot, 고정 protocol, worker·registry·serving 구현 범위.
- [74: QC agent 계약](74_QC_AGENT_CONTRACT.md), [75: Label agent 계약](75_LABEL_AGENT_CONTRACT.md), [76: MLOps agent 계약](76_MLOPS_AGENT_CONTRACT.md), [77: agent 실행](77_AGENT_COLLABORATION_EXECUTION.md): 각 변경 당시 상세 계약과 검증 기록. 현행 호출·승인 순서는 루트 문서와 실제 코드에서 확인한다.
- [81: 모델 학습 자동화·원천 감사](81_MODEL_TRAINING_AUTOMATION_AND_SOURCE_AUDIT.md): 82 이전 원천·모델 구현의 과거 기록.

2026-10-08 확인에서 API와 worker가 실행 중이어도 실제 승인·dataset·학습 이력·model registry·운영 모델은 0이다. 72 업무 키는 자료형별 부분 기준선이며 운영 모델 72개의 완료 기록이 아니다. 담당 승인 전 원천 검토 패킷이나 파일 집계, legacy 모델 후보 평가를 운영 승인으로 재사용하지 않는다.

JSON 집계는 해당 파일의 시점과 생성 방법을 함께 확인한다. 이전 집계 파일의 수치를 현행 결과로 바꾸거나 승인 영수증처럼 사용하지 않는다. 최신 읽기 전용 상태 요약은 [current_status.json](../../docs/current_status.json)에 별도로 기록한다.
