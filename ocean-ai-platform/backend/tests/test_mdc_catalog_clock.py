from datetime import datetime
import pytest
from app.services.mdc_sensor_catalog import source_datetime, catalog_records, catalog_version, checksum, sync_catalog


@pytest.mark.parametrize('raw,expected', [
    ('2023-01-01T09:00:00+09:00', datetime(2023,1,1)),
    ('2023-01-01T00:00:00Z', datetime(2023,1,1)),
    ('2023-01-01 09:00:00', None), ('2023-01-01', None),
    ('not a date', None), (None, None)])
def test_clock_never_infers_kst(raw, expected):
    assert source_datetime(raw) == expected


def test_naive_source_dates_are_preserved_and_flagged():
    raw = {'obs_post_id':'ST','te_code':'TE','obs_item_code':'WATER_TEMP','unit':'℃',
        'use_start_date':'2023-01-01 09:00:00','use_end_date':'2024-01-01'}
    result = catalog_records({'items':[raw], 'equipment':[{'obs_post_id':'ST','te_code':'TE'}]}, {'ST'})[0]
    assert result['valid_start'] is result['valid_end'] is None
    assert 'DATE_TIMEZONE_UNVERIFIED' in result['issues']
    assert 'HISTORICAL_VALIDITY_UNKNOWN' in result['issues']
    assert result['source_payload']['items'][0] == raw
    assert 'PHYSICAL_IDENTITY_REVIEW_REQUIRED' in result['issues']


def test_malformed_source_date_does_not_crash_catalog():
    row = {'obs_post_id':'ST','te_code':'TE','obs_item_code':'AIR_PRES','unit':'hPa','use_start_date':'bad'}
    result = catalog_records({'items':[row], 'equipment':[]}, {'ST'})[0]
    assert result['valid_start'] is None and 'SOURCE_DATE_INVALID' in result['issues']


def test_dry_run_and_apply_share_parser_version_and_preserve_old_versions(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.models.domain import StationMetadata, ObservationStandard
    from app.models.evidence import MDCSensorCatalog
    from app.scripts import reconcile_mdc_sensors as cli
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine); sessions = sessionmaker(bind=engine)
    data = {'items':[{'obs_post_id':'ST','te_code':'TE','obs_item_code':'WATER_TEMP','unit':'℃',
        'use_start_date':'2023-01-01 09:00:00'}], 'equipment':[], 'stations':[]}
    records = catalog_records(data, {'ST'}); old = checksum([(r['sensor_id'],r['source_hash']) for r in records])
    assert old != catalog_version(records)
    with sessions() as db:
        db.add(StationMetadata(station_id='ST',station_name='fixture',latitude=0.,longitude=0.))
        db.add(ObservationStandard(observation_id='O',station_id='ST',sensor_id='TEST_SENSOR',variable_code='WATER_TEMP',timestamp_utc=datetime(2023,1,1),standardization_version='fixture'))
        legacy = dict(records[0]); legacy['valid_start'] = datetime(2023,1,1)
        db.add(MDCSensorCatalog(catalog_version=old, **legacy)); db.commit()
    monkeypatch.setattr(cli,'SessionLocal',sessions); monkeypatch.setattr(cli,'engine',engine)
    dry = cli.reconcile(data); applied = cli.reconcile(data,apply=True)
    assert dry['catalog_version'] == applied['catalog_version'] == catalog_version(records)
    with sessions() as db:
        prior=db.get(MDCSensorCatalog,(records[0]['sensor_id'],old))
        current=db.get(MDCSensorCatalog,(records[0]['sensor_id'],applied['catalog_version']))
        assert prior.valid_start == datetime(2023,1,1) and current.valid_start is None
        assert current.source_payload == prior.source_payload
        # Existing content in the new version remains immutable on replay.
        current.valid_start=datetime(2023,1,1); db.commit()
        with pytest.raises(ValueError,match='Immutable catalog content conflict'):
            sync_catalog(db,data,{'ST'})
        current.valid_start=None; db.commit()
        current.source_hash='tampered'; db.commit()
        with pytest.raises(ValueError,match='Immutable catalog content conflict'):
            sync_catalog(db,data,{'ST'})
    engine.dispose()
