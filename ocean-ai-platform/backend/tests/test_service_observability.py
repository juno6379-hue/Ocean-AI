from datetime import datetime,timezone
from pathlib import Path
import uuid,json
from app.services import service_observability as s

def test_batch_pid_reuse_is_not_reported_as_confirmed_worker(monkeypatch):
    root=Path(__file__).parent/'.work'/('service-'+uuid.uuid4().hex);root.mkdir(parents=True)
    p=root/'status.json';p.write_text(json.dumps({'state':'COPYING','pid':123,'started_at':'2026-10-06T01:00:00+00:00','at':'2026-10-06T02:00:00+00:00'}),encoding='utf-8')
    monkeypatch.setattr(s,'windows_process',lambda pid:{'state':'PID_EXISTS','started_at':'2026-10-06T03:00:00+00:00'})
    r=s.batch_record('copy',p,datetime(2026,10,6,4,tzinfo=timezone.utc))
    assert r['process']['start_matches'] is False
    assert r['status']=='CHECK_DETAILS' and r['os_lock']=='NOT_CHECKED'
    assert r['age_seconds']==7200
    p.write_text('{partial',encoding='utf-8')
    assert s.batch_record('copy',p,datetime.now(timezone.utc))['status']=='RECORD_UNAVAILABLE'

def test_completed_record_does_not_probe_or_assume_live_process(monkeypatch):
    root=Path(__file__).parent/'.work'/('service-'+uuid.uuid4().hex);root.mkdir(parents=True)
    p=root/'status.json';p.write_text('{"state":"COMPLETE","pid":123}',encoding='utf-8')
    def forbidden(pid):raise AssertionError('Terminal PID must not be probed')
    monkeypatch.setattr(s,'windows_process',forbidden)
    r=s.batch_record('done',p,datetime.now(timezone.utc))
    assert r['status']=='REPORTED_COMPLETE' and r['process']['state']=='NOT_CHECKED'
