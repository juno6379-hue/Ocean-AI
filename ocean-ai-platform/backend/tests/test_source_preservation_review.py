from app.services.source_preservation_review import native_extent


def channel(last, rows=10):
    return {"grain": {"month": "2026-07", "source_group": "GD", "station_code": "DT_0001", "item_code": "AIR_PRES"},
            "raw_rows": rows, "last_valid_native_clock": last,
            "interval_and_grid_diagnostic": {"representative_interval_microseconds": 60000000}}


def test_july_tail_is_archive_extent_not_approved_outage():
    r = native_extent(channel("2026-07-30 03:31:00"))
    assert r["trailing_gap_native_seconds"] == 160080
    assert r["status"] == "TRAILING_NATIVE_EXTENT_GAP_CANDIDATE"
    assert r["source_clock_approved"] is False
    assert r["operational_gap_cause"] is None
    assert r["next_native_slot_candidate"] == "2026-07-30T03:32:00"


def test_end_extent_and_no_held_rows_are_separate():
    assert native_extent(channel("2026-07-31 23:59:00"))["trailing_gap_native_seconds"] == 0
    r = native_extent(channel(None, rows=0))
    assert r["status"] == "NO_CURRENT_HELD_ROWS"
    assert r["trailing_gap_native_seconds"] is None


def test_additive_metadata_keeps_original_rescan_receipt_path_and_sha(tmp_path):
    import json,sqlite3
    from app.services.source_preservation_review import review_migration
    from app.rag.ingestion_recovery import canonical,sha_file
    journal=tmp_path/'journal.sqlite3';c=sqlite3.connect(journal)
    c.executescript('CREATE TABLE scopes(name,source,target,state);CREATE TABLE files(scope,status,bytes,sha256);')
    target=tmp_path/'target';folder=target/'metadata/facility_registry/run';folder.mkdir(parents=True)
    manifest=folder/'manifest.json';manifest.write_bytes(canonical({'status':'PUBLISHED_REVIEW_ONLY','operating_facility_count':None,'files':{}}))
    c.execute('INSERT INTO scopes VALUES(?,?,?,?)',('integrated_lake',str(tmp_path/'source'),str(target),'COPY_VERIFIED'))
    c.execute('INSERT INTO files VALUES(?,?,?,?)',('integrated_lake','VERIFIED',1,'a'*64));c.commit();c.close()
    receipts=tmp_path/'receipts';receipts.mkdir();p=receipts/'verification-integrated_lake.json'
    p.write_bytes(canonical({'status':'FAILED','checked_at':'prior','errors':[{'kind':'target','path':str(manifest),'error':'UNINVENTORIED_FILE'}],
        'file_counts':{'source':{'files':1},'target':{'files':2}},'hash_basis':'prior copy hash'}))
    r=review_migration(journal,receipts)['rescan_receipts'][0]
    assert r['passed'] is True
    assert r['path']==str(p)
    assert r['sha256']==sha_file(p)
    assert r['additive_derived_files'][0]['path']==str(manifest)
