"""Loopback-only bounded synthetic analysis; no production dependency injection."""
import ipaddress
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from app.services.operation_simulation import scenarios, run_simulation

router = APIRouter(prefix='/api/operation-simulation', tags=['Synthetic quality process'])


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scenario_id: str = Field(min_length=1, max_length=32)
    as_of_day: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    as_of_time: str = Field(pattern=r'^\d{2}:\d{2}:\d{2}(\.\d{1,6})?$')


def local_only(request):
    try: allowed = ipaddress.ip_address(request.client.host).is_loopback if request.client else False
    except ValueError: allowed = False
    if not allowed: raise HTTPException(403, 'Synthetic quality analysis requires loopback access')


@router.get('/scenarios')
def list_scenarios(request: Request):
    local_only(request)
    return scenarios()


@router.post('/run')
async def run(request: Request):
    local_only(request)
    raw = await request.body()
    if len(raw) > 2048: raise HTTPException(413, 'Simulation requests are limited to 2 KiB')
    try: body = RunRequest.model_validate(json.loads(raw))
    except (ValueError, TypeError): raise HTTPException(422, 'Invalid bounded simulation request') from None
    from starlette.concurrency import run_in_threadpool
    try: return await run_in_threadpool(run_simulation, body.scenario_id, body.as_of_day, body.as_of_time)
    except (ValueError, OverflowError) as exc: raise HTTPException(422, str(exc)) from None
