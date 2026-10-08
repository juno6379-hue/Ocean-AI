"""Connection testing requires administrator identity and does not ingest data."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import routes_integrations as routes
from app.core.security import Actor,current_actor


def client(role):
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[current_actor]=lambda:Actor('isolated-test',role)
    return TestClient(app)


def test_viewer_cannot_read_or_probe_connections():
    c=client('viewer')
    assert c.get('/api/integrations').status_code==403
    assert c.post('/api/integrations/operational-postgres/test').status_code==403


def test_admin_probe_does_not_start_ingestion(monkeypatch):
    monkeypatch.setattr(routes,'probe',lambda source:{'connection':True,'read_probe':'ISOLATED_TEST'})
    r=client('admin').post('/api/integrations/operational-postgres/test')
    assert r.status_code==200
    assert r.json()['ingestion_started'] is False
    assert r.json()['approval_changed'] is False


def test_driver_error_never_returns_secrets(monkeypatch):
    def fail(source):raise ValueError('secret://private:password@host')
    monkeypatch.setattr(routes,'probe',fail)
    r=client('admin').post('/api/integrations/operational-postgres/test')
    assert r.json()['status']=='FAILED'
    assert 'password' not in r.text and 'secret://' not in r.text
