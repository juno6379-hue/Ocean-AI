# 파일 역할: 기존 자료를 변경하지 않고 사건 근거 및 학습 계보 테이블만 추가합니다.
import json
from sqlalchemy import inspect, text
from app.core.database import engine
from app.models import domain
from app.models.evidence import SensorAlias, EventEvidence, LabelReviewSnapshot, FeatureProvenance, DatasetMembership

TABLES=[SensorAlias.__table__,EventEvidence.__table__,LabelReviewSnapshot.__table__,
        FeatureProvenance.__table__,DatasetMembership.__table__]


def migrate():
    with engine.begin() as connection:
        if connection.dialect.name=='postgresql':
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('event-evidence-schema-v1'))"))
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        before=set(inspect(connection).get_table_names())
        repaired=[]
        # 과거 증분 마이그레이션에서 빠진 참조 키를 먼저 검사한다. 중복 원본은 삭제하지 않는다.
        for name,columns,index_name in [('document_index',['chunk_id'],'uq_document_chunk_evidence'),
                                        ('feature_definition',['feature_id','feature_version'],'uq_feature_definition_evidence')]:
            inspector=inspect(connection)
            unique=[set(r['column_names']) for r in inspector.get_unique_constraints(name)]
            unique += [set(r['column_names']) for r in inspector.get_indexes(name) if r['unique']]
            unique.append(set(inspector.get_pk_constraint(name)['constrained_columns']))
            if set(columns) not in unique:
                fields=','.join(columns)
                duplicate=connection.execute(text(f'SELECT {fields} FROM {name} GROUP BY {fields} HAVING count(*)>1 LIMIT 1')).first()
                if duplicate: raise RuntimeError(f'Duplicate reference keys in {name}; manual review required')
                connection.execute(text(f'CREATE UNIQUE INDEX {index_name} ON {name} ({fields})'))
                repaired.append(index_name)
        for table in TABLES: table.create(connection,checkfirst=True)
        return {'migration':'event-evidence-v1','created':[t.name for t in TABLES if t.name not in before],
                'verified':[t.name for t in TABLES if inspect(connection).has_table(t.name)],'added_reference_indexes':repaired}


if __name__=='__main__': print(json.dumps(migrate()))
