"""Independent expanded-data checks for the exact compact clock distribution."""
import copy
from datetime import datetime, timedelta
import hashlib
import json
import random

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.services.native_receipt_diagnostics import (
    ReceiptDiagnosticError, calculate_source, compact_points, publish_packets,
    receipt_diagnostics, run_statistics, validate_packet,
)


@pytest.mark.parametrize('seed', [7,23,97])
def test_overlapping_runs_match_expanded_samples(seed):
    rng=random.Random(seed)
    runs=[];values=[]
    for _ in range(300):
        start=rng.randrange(-80,80)*1_000_000
        step=rng.randrange(1,5)*1_000_000
        points=rng.randrange(1,16);count=rng.randrange(1,5)
        runs.append({'start':start,'step':step if points>1 else 0,'points':points,'count':count})
        values.extend((start+i*step)/1_000_000 for i in range(points) for _ in range(count))
    actual=run_statistics(runs)
    assert actual['min']==min(values) and actual['max']==max(values)
    assert actual['mean']==pytest.approx(np.mean(values),abs=1e-10)
    assert actual['p50']==pytest.approx(np.quantile(values,.5),abs=1e-10)
    assert actual['p95']==pytest.approx(np.quantile(values,.95),abs=1e-10)


def test_regular_histogram_is_lossless_and_small():
    points=[{'microseconds':-5000_000_000+i*60_000_000,'count':2} for i in range(10_000)]
    runs=compact_points(points)
    assert len(runs)==1
    expanded=[r['start']+i*r['step'] for r in runs for i in range(r['points']) for _ in range(r['count'])]
    assert expanded==[p['microseconds'] for p in points for _ in range(p['count'])]


@pytest.mark.parametrize('partitioned',[False,True])
def test_large_exact_source_packet_and_query_pooled_quantiles(tmp_path,monkeypatch,partitioned):
    if partitioned:
        from app.services import native_receipt_diagnostics
        monkeypatch.setattr(native_receipt_diagnostics,'NATIVE_RECEIPT_PARTITION_ROWS',1)
    observed=datetime(2026,7,1)
    received=datetime(2026,7,20)
    records=[{'OBS_POST_ID':'DT_0001','OBS_ITEM_CODE':'AIR_PRES',
              'OBS_TIME':(observed+timedelta(minutes=i)).isoformat(),
              'RECEIVE_TIME':received.isoformat()} for i in range(6000)]
    path=tmp_path/'dense.parquet'
    pq.write_table(pa.Table.from_pylist(records),path)
    entries=[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
    packet=calculate_source(entries,'GR_OBS_ST','test-snapshot',tmp_path,{'2026-07'})[0]
    row=packet['channels'][0]
    assert row['difference_histogram']==[] and len(row['difference_runs'])<=2
    validate_packet(packet)
    publish_packets([packet],tmp_path/'packets')
    result=receipt_diagnostics('GR_OBS_ST','2026-07','2026-07',snapshot='test-snapshot',root=tmp_path/'packets',source_root=tmp_path)
    differences=[(received-(observed+timedelta(minutes=i))).total_seconds() for i in range(6000)]
    actual=result['raw']['difference_seconds']
    assert actual['mean']==pytest.approx(np.mean(differences))
    assert actual['p95']==pytest.approx(np.quantile(differences,.95))
    assert result['raw']['comparable_pair_rows']==6000
    broken=copy.deepcopy(packet)
    broken['channels'][0]['difference_runs'][0]['points']-=1
    with pytest.raises(ReceiptDiagnosticError):validate_packet(broken)
    broken=copy.deepcopy(packet)
    broken['channels'][0]['difference_runs'][0]['step']=0
    with pytest.raises(ReceiptDiagnosticError):validate_packet(broken)


def test_memory_fallback_preserves_exact_grains_without_double_count(tmp_path, monkeypatch):
    import duckdb
    original_connect = duckdb.connect
    failures = []

    class BoundedConnection:
        def __init__(self):
            self.connection = original_connect(':memory:')

        def execute(self, query, parameters=None):
            if query.lstrip().startswith('WITH raw AS') and 'delta_us,count(*) AS n' in query and len(failures) < 2:
                failures.append(query)
                raise duckdb.OutOfMemoryException('bounded-memory fixture')
            return self.connection.execute(query, parameters) if parameters is not None else self.connection.execute(query)

        def close(self):
            self.connection.close()

    records = [{'OBS_POST_ID':station, 'OBS_ITEM_CODE':item,
                'OBS_TIME':'2026-07-01T00:00:00', 'RECEIVE_TIME':'2026-07-01T00:01:00'}
               for station in ('DT_0001', 'DT_0002') for item in ('AIR_PRES', 'AIR_TEMP') for _ in range(9)]
    path = tmp_path / 'multi-grain.parquet'
    pq.write_table(pa.Table.from_pylist(records), path)
    monkeypatch.setattr(duckdb, 'connect', lambda *args, **kwargs: BoundedConnection())
    packet = calculate_source([{'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}],
                              'GR_OBS_ST', 'test-snapshot', tmp_path, {'2026-07'})[0]
    validate_packet(packet)
    assert len(failures) == 2
    assert len(packet['channels']) == 4
    assert all(row['raw_rows'] == 9 for row in packet['channels'])
    assert packet['raw']['raw_rows'] == 36
    assert packet['raw']['difference_seconds']['mean'] == 60
