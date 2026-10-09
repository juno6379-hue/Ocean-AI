"""Development-only sandbox-token API. No operational authentication or DB."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from typing import Literal
from app.core.config import settings
from app.services import qc_sample as sample

router=APIRouter(prefix='/api/qc-sample',tags=['Isolated QC sample'])


def enabled(request: Request, response: Response):
    if not getattr(settings,'QC_SAMPLE_ENABLED',False) or settings.ENVIRONMENT.lower() not in ('development','test','local'):
        raise HTTPException(404,dict(code='QC_SAMPLE_DISABLED'))
    if request.query_params:
        raise HTTPException(422,dict(code='SAMPLE_QUERY_NOT_SUPPORTED'))
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'


def token(request: Request):
    values=request.headers.getlist('x-qc-sample-token')
    if len(values)!=1 or not values[0].startswith('qc-sample-') or len(values[0])>200:
        raise HTTPException(401,dict(code='SAMPLE_TOKEN_REQUIRED',operational_writes=0))
    # Bearer identities are never read or accepted by this API.
    if request.headers.get('authorization'):
        raise HTTPException(401,dict(code='SAMPLE_OPERATIONAL_IDENTITY_NOT_ACCEPTED',operational_writes=0))
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


@router.get('/sessions/{session_id}/cases/{case_id}',dependencies=[Depends(enabled)])
def get_case(session_id:str,case_id:str,credential:str=Depends(token)):
    return call(sample.detail,credential,session_id,case_id)


@router.post('/sessions/{session_id}/cases/{case_id}/review',dependencies=[Depends(enabled)])
def post_review(session_id:str,case_id:str,body:ReviewBody,credential:str=Depends(token)):
    return call(sample.review,credential,session_id,case_id,body.action,body.comment,
                body.expected_revision,body.recommendation_sha256,body.request_key)


@router.post('/sessions/{session_id}/reset',dependencies=[Depends(enabled)])
def post_reset(session_id:str,body:ResetBody,credential:str=Depends(token)):
    return call(sample.reset,credential,session_id,body.expected_session_revision,body.request_key)
