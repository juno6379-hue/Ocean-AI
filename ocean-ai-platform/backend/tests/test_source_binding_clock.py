"""Explicit ingest-clock roundtrip in isolation, without production DDL."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import StatementError
from app.core.database import Base
from app.core.security import Actor
from app.models.domain import StationMetadata, SensorMetadata
from app.models.source_observation_binding import SourceObservationBinding
from app.scripts.migrate_binding_clock_20261009 import migrate, DDL
from app.services import qc_candidate_review as q
from app.services import source_contract_authority as authority
from app.services import source_contract_snapshot as snapshot
from app.services.qc_overview import resolve_window
from test_source_contract_snapshot import source_packet
from test_qc_candidate_review import fixture, window

UTC=timezone.utc
CLOCK=datetime(2025,2,1,0,6,tzinfo=UTC)


class FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return CLOCK.astimezone(tz) if tz else CLOCK.replace(tzinfo=None)


def test_postgres_clock_column_and_default_dry_run_never_backfill_or_connect():
    table=SourceObservationBinding.__table__
    column=table.c.bound_at_utc
    assert column.nullable and column.default is None and column.server_default is None
    ddl=str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert 'bound_at_utc TIMESTAMP WITH TIME ZONE' in ddl
    fake=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    result=migrate(fake)
    assert result==dict(applied=False,sql=DDL,legacy_backfill=False,server_default=None,data_writes=0)
    assert 'DEFAULT' not in DDL and 'UPDATE' not in DDL


def test_legacy_created_at_never_becomes_binding_availability():
    obs,binding,receipt,raw=fixture()
    for created_at in (datetime(2026,7,9,10,6),datetime(2026,7,9,10,6,tzinfo=UTC)):
        binding.created_at=created_at;binding.bound_at_utc=None
        with pytest.raises(q.CandidateError,match='BINDING_RECORD_AVAILABILITY_UNVERIFIED'):
            q._registered_row(obs,binding,receipt,raw,window())
    binding.bound_at_utc=datetime(2026,7,9,10,6,tzinfo=UTC)
    assert q._registered_row(obs,binding,receipt,raw,window())['available_at'].endswith('+00:00')
    binding.bound_at_utc=datetime(2026,7,9,12,tzinfo=UTC)+timedelta(microseconds=1)
    with pytest.raises(q.CandidateError,match='POST_CUTOFF_SOURCE_OR_BINDING_AVAILABLE'):
        q._registered_row(obs,binding,receipt,raw,window())


def test_new_clock_rejects_naive_writes_and_sqlite_roundtrip_preserves_explicit_utc():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    values=dict(observation_id='O',contract_id='C',approval_history_id=1,receipt_sha256='a'*64,
        source_sha256='b'*64,parquet_sha256='c'*64,source_row_locator='row=1',exact_scope_key='d'*64,payload={},created_by='ISOLATED')
    with Session(engine) as db:
        db.add(SourceObservationBinding(**values,bound_at_utc=CLOCK.replace(tzinfo=None)))
        with pytest.raises(StatementError,match='BINDING_CLOCK_EXPLICIT_OFFSET_REQUIRED'): db.flush()
        db.rollback()
        db.add(SourceObservationBinding(**values,bound_at_utc=CLOCK.astimezone(timezone(timedelta(hours=9)))))
        db.commit();db.expire_all()
        row=db.get(SourceObservationBinding,'O')
        assert row.bound_at_utc==CLOCK and row.bound_at_utc.utcoffset()==timedelta(0)
        assert row.created_at.tzinfo is None  # legacy field intentionally unchanged
    engine.dispose()


def test_real_isolated_approved_ingest_roundtrip_is_readable_and_idempotent(tmp_path,monkeypatch):
    monkeypatch.setattr(authority,'SOURCE_ROOT',tmp_path)
    monkeypatch.setattr(authority,'datetime',FrozenClock)
    monkeypatch.setattr(snapshot,'datetime',FrozenClock)
    packet=source_packet(tmp_path,'ISOLATED_EVENT',with_receive=True)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(StationMetadata(station_id='ST1',station_name='Isolated station'))
        db.add(SensorMetadata(station_id='ST1',sensor_id='S1',variable_code='TIDE'));db.commit()
        request=authority.request_contract(db,packet,Actor('isolated-operator','operator'))
        approved=authority.decide_contract(db,packet['contract_id'],request['packet_sha256'],'APPROVED',Actor('isolated-reviewer','reviewer'))
        first=snapshot.ingest_approved_source(db,approved['receipt'],approved['receipt_sha256'],Actor('isolated-operator','operator'))
        db.commit();db.expire_all()
        bindings=db.query(SourceObservationBinding).all()
        assert first['inserted']==3 and all(row.bound_at_utc==CLOCK for row in bindings)
        assert all(row.payload==approved['receipt']['observations'][row.observation_id] and row.created_at.tzinfo is None for row in bindings)
        actual=q.registered_rows(db,resolve_window(now=CLOCK+timedelta(minutes=1)))
        assert actual['selected_count']==3 and len(actual['rows'])==3 and actual['excluded_counts']=={}
        assert all(row['available_at']==CLOCK.isoformat() for row in actual['rows'])
        plus9=timezone(timedelta(hours=9));end=CLOCK+timedelta(minutes=1)
        offset_window=resolve_window('REGISTERED','custom',date_from='2025-02-01T09:00:00+09:00',
            date_to=end.astimezone(plus9).isoformat(),now=end)
        offset_rows=q.registered_rows(db,offset_window)
        assert {r['observation_id'] for r in offset_rows['rows']}=={r['observation_id'] for r in actual['rows']}
        # Today's first nine local hours include the corresponding previous UTC
        # day. This preserves offsets by conversion, never by relabeling.
        local_today=q.registered_rows(db,resolve_window(now=end.astimezone(plus9)))
        assert local_today['selected_count']==3 and len(local_today['rows'])==3
        boundary=resolve_window('REGISTERED','custom',date_from='2025-02-01T09:01:00+09:00',
            date_to=end.astimezone(plus9).isoformat(),now=end)
        assert {r['observation_id'] for r in q.registered_rows(db,boundary)['rows']}=={'O1','O2'}
        second=snapshot.ingest_approved_source(db,approved['receipt'],approved['receipt_sha256'],Actor('isolated-operator','operator'))
        assert second['already_bound']==3 and second['inserted']==0
        assert all(row.bound_at_utc==CLOCK for row in db.query(SourceObservationBinding).all())
        # Replaying ingest does not retroactively fill a legacy NULL clock.
        bindings[0].bound_at_utc=None;db.commit()
        snapshot.ingest_approved_source(db,approved['receipt'],approved['receipt_sha256'],Actor('isolated-operator','operator'))
        assert db.get(SourceObservationBinding,bindings[0].observation_id).bound_at_utc is None
        after=q.registered_rows(db,resolve_window(now=CLOCK+timedelta(minutes=1)))
        assert len(after['rows'])==2 and after['excluded_counts']=={'BINDING_RECORD_AVAILABILITY_UNVERIFIED':1}
    engine.dispose()
