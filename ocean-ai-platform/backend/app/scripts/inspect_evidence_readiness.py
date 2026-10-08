# 파일 역할: 실제 문서·관측·사건·승인 자료의 연결 가능 범위를 읽기 전용으로 점검합니다.
import json
from pathlib import Path
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.domain import (ObservationRaw, ObservationStandard, DocumentIndex, EventRegistry, AILabel,
    QCRuleResult, OperationLog, SensorMetadata, FeatureValue, DatasetRegistry)


def inspect_readiness():
    with SessionLocal() as db:
        result = {}
        for model, field in [(ObservationStandard, ObservationStandard.timestamp_utc),
                             (DocumentIndex, DocumentIndex.document_date)]:
            count, start, end = db.query(func.count(), func.min(field), func.max(field)).select_from(model).one()
            result[model.__tablename__] = {'count': count, 'start': str(start), 'end': str(end)}
        for model in [EventRegistry, AILabel, QCRuleResult, OperationLog, FeatureValue, DatasetRegistry]:
            result[model.__tablename__] = db.query(model).count()
        result['observation_scopes'] = [list(r) for r in db.query(ObservationStandard.station_id,
            ObservationStandard.sensor_id, ObservationStandard.variable_code,
            func.min(ObservationStandard.timestamp_utc), func.max(ObservationStandard.timestamp_utc),
            func.count()).group_by(ObservationStandard.station_id, ObservationStandard.sensor_id,
                                  ObservationStandard.variable_code).limit(30)]
        result['document_years'] = [list(r) for r in db.query(func.extract('year',DocumentIndex.document_date),func.count()).group_by(func.extract('year',DocumentIndex.document_date))]
        result['sensors'] = db.query(SensorMetadata).count()
        # DB 행 수와 실제 관측 출처를 구별한다. SIMULATED 행은 실사건 준비 건수에서 제외한다.
        from app.services.observation_provenance import raw_for_standard, source_issue
        sources = {}
        eligible = 0
        for observation in db.query(ObservationStandard):
            raw = raw_for_standard(db, observation)
            source = raw.source_system if raw else 'MISSING_RAW'
            sources[source] = sources.get(source, 0) + 1
            if not source_issue(raw) and 'TEST' not in (source or '').upper(): eligible += 1
        result['standard_source_counts'] = sources
        result['non_simulated_standard_count'] = eligible
        return result


if __name__ == '__main__':
    result = inspect_readiness()
    path = Path('backend/app/data/document_pipeline/evidence_readiness.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, default=str))
