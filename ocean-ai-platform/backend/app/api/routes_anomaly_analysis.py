"""Loopback, bounded development analysis; no approval/DB/registry writes."""
import ipaddress
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.ml.anomaly_artifact import MAX_JSON_BYTES
from app.services.anomaly_analysis import fit_analysis, analyze_series

router=APIRouter(prefix="/api/anomaly-analysis",tags=["Development anomaly analysis"])


async def local_payload(request:Request):
    try:
        if not request.client or not ipaddress.ip_address(request.client.host).is_loopback:
            raise ValueError()
    except ValueError:
        raise HTTPException(403,"Development anomaly analysis is limited to loopback clients")
    if len(await request.body()) > MAX_JSON_BYTES:
        raise HTTPException(413,"Development analysis request exceeds 4 MiB")


class FitRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    series:dict
    protocol:dict


class AnalyzeRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    series:dict
    artifact:dict


@router.post("/fit",dependencies=[Depends(local_payload)])
def fit(req:FitRequest):
    return fit_analysis(req.series,req.protocol)


@router.post("/analyze",dependencies=[Depends(local_payload)])
def analyze(req:AnalyzeRequest):
    return analyze_series(req.series,req.artifact)
