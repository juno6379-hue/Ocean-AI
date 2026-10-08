# Dataset Version Registry

현행화: 2026-10-08

## Registry와 참여 목록

[DatasetRegistry](../ocean-ai-platform/backend/app/models/domain.py)는 ID·이름·버전·분할, 관측소·센서·변수 범위, 반개방 기간 `[period_start, period_end)`, 샘플·QC 등급 수, Feature·Label·전처리·QC 규칙 버전, 상태·내용 hash·승인자를 저장한다. `dataset_name + dataset_version`은 유일하며 같은 `dataset_name`이 하나의 분할 실험군이다.

분할 종류는 `TRAIN`, `VALIDATION`, `TEST`, `BLIND_TEST`, `RETRAINING_POOL`이다. 현재 모델 비교 실행기는 명시적으로 고정한 `TRAIN`/`VALIDATION`/`TEST` 세 분할을 사용한다. `BLIND_TEST` 등록 지원이 별도 맹검 평가 실행 완료를 뜻하지 않는다. Pool도 평가 참여 목록으로 자동 승격하지 않는다.

`DatasetMembership`은 정확한 observation·label·event ID와 snapshot hash를 기록한다. 등록 요청의 샘플 수만 믿지 않고 build에서 실제 포함한 행을 계산한다. 관측 원천이 SIMULATED이거나 승인 Label·사건·Feature 근거가 없으면 검증 오류로 남긴다.

## 승인 원천에서 snapshot v2까지

1. `POST /api/datasets/source-candidates`는 선택한 Parquet와 manifest SHA·원천 범위의 후보를 만든다. 기본 제한은 500행, 최대 5,000행이다. 후보 JSON은 운영 membership이나 승인 영수증이 아니다.
2. 담당자는 [원천 계약 승인](17_HUMAN_IN_THE_LOOP.md)을 수행한다. 실제 source receipt를 `POST /api/datasets/source-ingest`에 전달하면 최신 승인·실제 원천 행을 재검증하고 멱등 ingest 및 `SourceObservationBinding`을 만든다. `register_metadata`는 명시적 선택 사항이다.
3. 사건·관측·QC·문서·운영 이력, 승인 Label과 내용 hash, Feature 정의·값·출처를 연결한다. source ingest만으로 이 단계가 생기지 않는다.
4. 고정 `SPLIT_PROTOCOL`, `EVALUATION_PROTOCOL`, `ACCEPTANCE_POLICY`를 승인한다. build 요청의 `dependencies`는 role·허용된 JSON 경로·SHA를 명시한다.
5. build는 `event-evidence-dataset-2` snapshot에 source receipt와 세 정책의 불변 사본·hash를 포함한다. 원문/Parquet 전체를 snapshot 디렉터리에 복제하는 방식은 아니다.
6. validate와 reviewer approve는 현재 DB 참여 목록·원문 파일·승인 이력을 다시 확인한다. 승인 후에는 같은 Dataset을 rebuild하지 않고 새 버전을 만든다.

원문 ID와 canonical ID, SQLPLUS padding 변환, 타입을 보존한 수심·scope key, 원문 QC·수신 시각을 유지한다. typed 관측은 승인된 성분별 binding과 payload를 그대로 동결하며 scalar 값을 발명하지 않는다. source reviewer와 Dataset reviewer는 각자의 실제 승인 이력에 결합된다.

기존 `event-evidence-dataset-1` 구조는 원천 의존성을 동결하지 않는다. 현재 승인 경로는 v2와 실제 승인 source/protocol 의존성을 요구하므로 v1에 `APPROVED` 문자열만 넣어 사용할 수 없다. 실제 legacy 자동 전환은 수행하지 않았다.

## 고정 분할과 누수 검사

[dataset_lineage.py](../ocean-ai-platform/backend/app/services/dataset_lineage.py)와 [comparison_runner.py](../ocean-ai-platform/backend/app/ml/comparison_runner.py)는 등록·snapshot·실행 시 서로 다른 깊이의 검사를 수행한다.

| 전략 | 의도와 검사 |
|---|---|
| `station_holdout` | 관측소를 분할 간 분리한다. 승인 전략이 없는 기존 등록 경로의 기본 엄격 검사다. |
| `temporal_with_purge` | 실제 동일 station/sensor episode의 시간 분할을 허용하되 분할 순서·embargo·Feature window·origin·target 및 사건/원천/문서 누수를 검사한다. |
| `sensor_transition_holdout` | 센서 전환을 평가 대상으로 삼고 센서·episode 범위와 시간 경계를 검증한다. |

전략 완화는 승인된 프로토콜을 받는 `/register-reviewed` 경로에서만 가능하다. 같은 물리 episode를 다른 ID로 발명해 분리를 통과시킬 수 없다. `*` 범위는 전체 포함을 뜻하며 빈 범위·음수 건수·잘못된 기간·참여 목록 불일치는 거부한다. 원천 행/typed 성분 셀·사건·문서 family의 중복도 모델 preflight에서 확인한다.

프로토콜은 정확한 Dataset ID, 각 분할 참여 ID digest·기간·embargo, 잠긴 holdout을 명시한다. Feature 출처의 실제 `available_at`과 `qc_available_at`은 선언된 Feature 가용 시각 및 forecast origin보다 늦으면 사용할 수 없다. 원천 계약·binding 누락/변조도 차단한다. 길이에 따른 trainer의 60/20/20은 이 고정 분할의 대체가 아니다.

## API와 상태

```text
GET  /api/datasets?dataset_split=TRAIN
POST /api/datasets
POST /api/datasets/register-reviewed
POST /api/datasets/source-candidates
POST /api/datasets/source-ingest
GET  /api/datasets/{dataset_id}
POST /api/datasets/{dataset_id}/build
POST /api/datasets/{dataset_id}/validate
POST /api/datasets/{dataset_id}/approve
GET  /api/datasets/{dataset_id}/lineage
```

신규 등록은 `DRAFT`만 허용한다. 정상 경로는 `DRAFT → BUILT → VALIDATED → APPROVED`다. validate가 반환하는 `INVALID`는 오류 응답 상태이고, 이미 `VALIDATED`였던 행은 오류 발생 시 `BUILT`로 되돌린다. approval 이력의 `snapshot_sha256=<data_hash>`와 snapshot 파일 bytes·DB membership이 모두 일치해야 한다.

2026-10-08 13:09 KST 운영 읽기 전용 확인에서 Dataset Registry와 source binding·approval 이력은 모두 0이다. 구현된 freeze/검증 경로와 실제 승인 Dataset 보유는 구분한다. 코드 근거: [routes_datasets.py](../ocean-ai-platform/backend/app/api/routes_datasets.py), [source_contract_snapshot.py](../ocean-ai-platform/backend/app/services/source_contract_snapshot.py), [binding 모델](../ocean-ai-platform/backend/app/models/source_observation_binding.py). 이어지는 학습·배포는 [19번 문서](19_MLOPS_VERSION_AND_EVALUATION.md)에 있다.
