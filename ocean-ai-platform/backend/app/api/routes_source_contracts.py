"""Human source review and scoped system-policy mapping receipts."""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import Actor, current_actor, require_reviewer
from app.models.source_contracts import SourceContractPacket, SourceContractDecision
from app.services import source_contract_authority as authority
from app.services import source_auto_mapping as auto

router = APIRouter(prefix='/api/source-contracts', tags=['Source Contract Review'])


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    packet: dict[str, Any]


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_packet_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['APPROVED', 'REJECTED', 'REVOKED']
    comment: str = Field(default='', max_length=4000)


def _error(exc):
    status = 404 if exc.code == 'SOURCE_CONTRACT_NOT_FOUND' else 409
    if exc.code in {'INVALID_REVIEW_PACKET', 'SOURCE_DECISION_UNSUPPORTED'}:
        status = 422
    if exc.code in {'AUTHENTICATED_OPERATOR_REQUIRED', 'AUTHENTICATED_REVIEWER_REQUIRED'}:
        status = 403
    raise HTTPException(status, {'code':exc.code, 'detail':exc.detail})


@router.get('')
def list_packets(db: Session = Depends(get_db)):
    rows = db.query(SourceContractPacket).order_by(SourceContractPacket.created_at.desc()).limit(200).all()
    return {'packets':[{'contract_id':row.contract_id, 'status':row.status, 'packet_sha256':row.packet_sha256,
        'requested_by':row.requested_by, 'approval_mode':'SYSTEM_POLICY' if row.payload.get('schema_version')==auto.SCHEMA else 'HUMAN_REVIEW',
        'approval_scope':row.payload.get('approval_scope','SOURCE_IDENTITY_UNIT_CLOCK_QC'),
        'readiness_errors':auto.packet_errors(row.payload) if row.payload.get('schema_version')==auto.SCHEMA else authority.packet_errors(row.payload)} for row in rows]}


@router.get('/auto-mapping/status')
def auto_mapping_status(db: Session = Depends(get_db)):
    return auto.summary(db)


@router.post('/request')
def request_review(req: ReviewRequest, db: Session = Depends(get_db), actor: Actor = Depends(current_actor)):
    try:
        result = authority.request_contract(db, req.packet, actor)
        db.commit()
        return result
    except authority.SourceContractError as exc:
        db.rollback()
        _error(exc)
    except Exception:
        db.rollback()
        raise


@router.get('/{contract_id}')
def get_packet(contract_id: str, db: Session = Depends(get_db)):
    row = db.get(SourceContractPacket, contract_id)
    if row is None:
        raise HTTPException(404, 'Source contract not found')
    if authority.receipt_sha256(row.payload) != row.packet_sha256:
        raise HTTPException(503, 'Review packet integrity failed')
    return {'contract_id':row.contract_id, 'status':row.status, 'packet_sha256':row.packet_sha256,
        'packet':row.payload, 'readiness_errors':auto.packet_errors(row.payload) if row.payload.get('schema_version')==auto.SCHEMA else authority.packet_errors(row.payload)}


@router.post('/{contract_id}/decision')
def decide_review(contract_id: str, req: ReviewDecision, db: Session = Depends(get_db), actor: Actor = Depends(require_reviewer)):
    try:
        if contract_id.startswith('auto-map-') and db.get_bind().dialect.name == 'postgresql':
            from sqlalchemy import text
            try:
                lock_key = int(contract_id[-15:], 16)
            except ValueError:
                raise authority.SourceContractError('AUTO_SOURCE_DECISION_UNSUPPORTED')
            # Revocation shares the ingestion lock: a committed batch finishes,
            # then the next batch must see the revoked contract.
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_key})
        packet = db.get(SourceContractPacket, contract_id)
        if packet and packet.payload.get('schema_version') == auto.SCHEMA:
            if req.decision != 'REVOKED' or packet.status != 'APPROVED' or req.expected_packet_sha256 != packet.packet_sha256:
                raise authority.SourceContractError('AUTO_SOURCE_DECISION_UNSUPPORTED')
            packet.status = 'REVOKED'
            from app.models.domain import ApprovalHistory, AuditLog
            db.add(ApprovalHistory(approval_type='SOURCE_CONTRACT',target_id=contract_id,requested_by=packet.requested_by,
                                  approved_by=None,approval_status='REVOKED',comment=actor.user_id+': '+req.comment))
            db.add(AuditLog(actor=actor.user_id, action='SOURCE_POLICY_REVOKED', resource_type='SOURCE_CONTRACT',
                           resource_id=contract_id, detail_json={'comment': req.comment}))
            db.commit()
            return {'contract_id':contract_id,'status':'REVOKED','approval_complete':False}
        result = authority.decide_contract(db, contract_id, req.expected_packet_sha256, req.decision, actor, req.comment)
        db.commit()
        return result
    except authority.SourceContractError as exc:
        db.rollback()
        _error(exc)
    except Exception:
        db.rollback()
        raise


@router.get('/{contract_id}/receipt')
def get_receipt(contract_id: str, db: Session = Depends(get_db)):
    row = db.query(SourceContractDecision).filter_by(contract_id=contract_id).order_by(SourceContractDecision.approval_history_id.desc()).first()
    if row is None:
        raise HTTPException(409, 'No authenticated source decision exists')
    try:
        if row.receipt.get('schema_version') == auto.RECEIPT_SCHEMA:
            auto.verify_receipt(db, row.receipt, row.receipt_sha256)
        else:
            authority.verify_approved_receipt(db, row.receipt, row.receipt_sha256)
    except authority.SourceContractError as exc:
        _error(exc)
    return Response(content=authority.canonical_bytes(row.receipt), media_type='application/json',
        headers={'X-Content-SHA256':row.receipt_sha256, 'Cache-Control':'no-store'})
