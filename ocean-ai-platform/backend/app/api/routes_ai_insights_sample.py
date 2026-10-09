"""Opt-in, isolated synthetic AI API; never operational authentication or DB."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.core.config import settings
from app.services import ai_insights_sample as sample

router=APIRouter(prefix='/api/ai-insights-sample',tags=['Isolated AI insights sample'])


def enabled(request:Request,response:Response):
    if not getattr(settings,'AI_INSIGHTS_SAMPLE_ENABLED',False) or settings.ENVIRONMENT.lower() not in ('development','test','local'):
        raise HTTPException(404,dict(code='AI_INSIGHTS_SAMPLE_DISABLED'))
    if 'authorization' in request.headers or 'cookie' in request.headers:
        raise HTTPException(401,dict(code='AI_SAMPLE_OPERATIONAL_IDENTITY_NOT_ACCEPTED',operational_writes=0))
    if request.query_params:raise HTTPException(422,dict(code='AI_SAMPLE_QUERY_NOT_SUPPORTED'))
    if len(request.url.path)>512:raise HTTPException(422,dict(code='AI_SAMPLE_PATH_TOO_LONG'))
    length=request.headers.get('content-length')
    if length is not None and (not length.isdigit() or int(length)>8192):
        raise HTTPException(413,dict(code='AI_SAMPLE_REQUEST_TOO_LARGE'))
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Content-Type-Options']='nosniff'


def token(request:Request):
    values=request.headers.getlist('x-ai-sample-token')
    if len(values)!=1 or not values[0].isascii() or not values[0].startswith('ai-sample-') or len(values[0])>200:
        raise HTTPException(401,dict(code='AI_SAMPLE_TOKEN_REQUIRED',operational_writes=0))
    return values[0]


class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$')


class ReviewBody(Body):
    action:Literal['COMMENT','APPROVE','HOLD','REJECT','RESUME']
    comment:str=Field(min_length=1,max_length=2000)
    expected_revision:StrictInt=Field(ge=1)
    recommendation_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')


class ResetBody(Body):
    expected_session_revision:StrictInt=Field(ge=1)


def call(function,*args):
    try:return function(*args)
    except sample.SampleError as error:
        raise HTTPException(error.status,dict(code=error.code,operational_writes=0,source_reads=0)) from None


@router.get('/context',dependencies=[Depends(enabled)])
def get_context():return call(sample.context)


@router.post('/sessions',dependencies=[Depends(enabled)])
def post_session(body:Body,credential:str=Depends(token)):
    return call(sample.create_session,credential,body.request_key)


@router.get('/sessions/{session_id}/overview',dependencies=[Depends(enabled)])
def get_overview(session_id:str,credential:str=Depends(token)):
    return call(sample.overview,credential,session_id)


@router.get('/sessions/{session_id}/scenarios/{scenario_id}',dependencies=[Depends(enabled)])
def get_scenario(session_id:str,scenario_id:str,credential:str=Depends(token)):
    return call(sample.detail,credential,session_id,scenario_id)


@router.post('/sessions/{session_id}/scenarios/{scenario_id}/review',dependencies=[Depends(enabled)])
def post_review(session_id:str,scenario_id:str,body:ReviewBody,credential:str=Depends(token)):
    return call(sample.review,credential,session_id,scenario_id,body.action,body.comment,
                body.expected_revision,body.recommendation_sha256,body.request_key)


@router.get('/sessions/{session_id}/scenarios/{scenario_id}/report',dependencies=[Depends(enabled)])
def get_report(session_id:str,scenario_id:str,credential:str=Depends(token)):
    return call(sample.report,credential,session_id,scenario_id)


@router.post('/sessions/{session_id}/reset',dependencies=[Depends(enabled)])
def post_reset(session_id:str,body:ResetBody,credential:str=Depends(token)):
    return call(sample.reset,credential,session_id,body.expected_session_revision,body.request_key)
