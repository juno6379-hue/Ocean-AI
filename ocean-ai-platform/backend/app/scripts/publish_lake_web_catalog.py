"""Publish immutable file lineage and monthly coverage to PostgreSQL.

This does not COPY billions of observations into observation_raw. The web reads
values from the verified Parquet adapter and joins evidence by snapshot/channel.
Re-running a published snapshot is a no-op; different snapshots coexist.
"""
import json
from sqlalchemy import text
from psycopg2.extras import execute_values, Json
import pyarrow.parquet as pq
from app.core.database import engine
from app.services.lake_browser import context, monthly_assets, history


def main():
    view, coverage = context()
    catalog = view/'file-only-timeseries.duckdb'
    assets = monthly_assets(str(catalog),catalog.stat().st_mtime_ns)
    old_assets, old_coverage = history()
    rows = pq.read_table(coverage).to_pylist()+old_coverage
    assets = assets+old_assets
    con=engine.raw_connection()
    try:
        cur=con.cursor()
        cur.execute('''CREATE SCHEMA IF NOT EXISTS lake_serving;
          CREATE TABLE IF NOT EXISTS lake_serving.snapshot(
            snapshot_id text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
            asset_count bigint NOT NULL, coverage_count bigint NOT NULL, status text NOT NULL);
          CREATE TABLE IF NOT EXISTS lake_serving.source_asset(
            snapshot_id text NOT NULL REFERENCES lake_serving.snapshot,
            parquet_path text NOT NULL, source_group text NOT NULL, lineage jsonb NOT NULL,
            PRIMARY KEY(snapshot_id,parquet_path));
          CREATE TABLE IF NOT EXISTS lake_serving.channel_month(
            snapshot_id text NOT NULL REFERENCES lake_serving.snapshot,
            row_number bigint NOT NULL,source_group text NOT NULL,station_code text NOT NULL,
            item_code text NOT NULL,month date NOT NULL,held_rows bigint NOT NULL,evidence jsonb NOT NULL,
            PRIMARY KEY(snapshot_id,row_number));
          CREATE INDEX IF NOT EXISTS lake_channel_lookup ON lake_serving.channel_month
            (snapshot_id,source_group,station_code,month);''')
        cur.execute('SELECT asset_count,coverage_count,status FROM lake_serving.snapshot WHERE snapshot_id=%s',[view.name])
        previous=cur.fetchone()
        if previous:
            if previous != (len(assets),len(rows),'RAW_UNAPPROVED'):
                raise RuntimeError('Published snapshot differs; create a new version')
            con.rollback();print(json.dumps({'snapshot':view.name,'status':'ALREADY_PUBLISHED','assets':len(assets),'coverage':len(rows)}));return
        cur.execute('INSERT INTO lake_serving.snapshot(snapshot_id,asset_count,coverage_count,status) VALUES(%s,%s,%s,%s)',[view.name,len(assets),len(rows),'RAW_UNAPPROVED'])
        as_json=lambda v:Json(v,dumps=lambda x:json.dumps(x,ensure_ascii=False,default=str))
        execute_values(cur,'INSERT INTO lake_serving.source_asset VALUES %s',[(view.name,a['parquet_path'],a['source_group'],as_json(a)) for a in assets],page_size=500)
        execute_values(cur,'INSERT INTO lake_serving.channel_month VALUES %s',[(view.name,i,r['source_group'],r['station_code'],r['item_code'],r['month'],r['held_rows'],as_json(r)) for i,r in enumerate(rows)],page_size=500)
        cur.execute('SELECT count(*) FROM lake_serving.channel_month WHERE snapshot_id=%s',[view.name]);assert cur.fetchone()[0]==len(rows)
        cur.execute('SELECT count(*) FROM lake_serving.source_asset WHERE snapshot_id=%s',[view.name]);assert cur.fetchone()[0]==len(assets)
        con.commit()
        print(json.dumps({'snapshot':view.name,'status':'PUBLISHED','assets':len(assets),'coverage':len(rows),'values_storage':'PARQUET','approval':'UNAPPROVED'}))
    except Exception:
        con.rollback();raise
    finally:
        con.close()


if __name__=='__main__':main()
