"""Bounded, read-only proposals; never creates labels, approvals or membership."""
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from app.models.domain import (ObservationStandard, QCRuleResult, EventRegistry,
                               DatasetRegistry, DocumentIndex)
from app.models.evidence import EventEvidence, DatasetMembership
from app.services.event_evidence import digest, validate_scope, utc
from app.services.observation_provenance import raw_for_standard, source_issue

MAX_OBSERVATIONS = 100
MAX_DATASET_ROWS = 500
MAX_EVIDENCE = 1000


def _ids(request, key, limit=MAX_OBSERVATIONS):
    values = request.get(key) or []
    if not isinstance(values, list) or len(values) > limit or any(
            not isinstance(value, str) or not value.strip() for value in values):
        raise HTTPException(422, f'{key} must contain at most {limit} nonempty IDs')
    return sorted(set(values))


def _base(candidate_id, **values):
    return dict(candidate_id=candidate_id, status='NEEDS_EVIDENCE',
                human_label=None, error_cause='unknown', training_eligible=False,
                persisted=False, **values)


def _observation_candidate(db, row, event=None):
    raw = raw_for_standard(db, row)
    blockers = []
    issue = source_issue(raw)
    if issue:
        blockers.append(issue)
    if not row.sensor_id:
        blockers.append('physical_sensor_unresolved')
    else:
        try:
            validate_scope(db, row.station_id, row.sensor_id, row.variable_code)
        except HTTPException:
            blockers.append('sensor_scope_unverified')
    qc = db.query(QCRuleResult).filter_by(observation_id=row.observation_id).order_by(
        QCRuleResult.qc_result_id).limit(MAX_OBSERVATIONS + 1).all()
    if len(qc) > MAX_OBSERVATIONS:
        blockers.append('qc_result_limit_exceeded')
    if not qc:
        blockers.append('qc_results_missing')
    if event is None:
        blockers.append('closed_evidence_event_required')
    else:
        if event.event_end is None or event.event_start >= event.event_end:
            blockers.append('closed_evidence_event_required')
        elif not event.event_start <= row.timestamp_utc < event.event_end:
            blockers.append('observation_outside_event')
        if any(getattr(event, key) != getattr(row, key) for key in
               ('station_id', 'sensor_id', 'variable_code')):
            blockers.append('event_scope_mismatch')
        links = db.query(EventEvidence).filter_by(event_id=event.event_id).limit(MAX_EVIDENCE + 1).all()
        if len(links) > MAX_EVIDENCE:
            blockers.append('event_evidence_limit_exceeded')
        if not any(link.observation_id == row.observation_id for link in links):
            blockers.append('observation_event_link_missing')
        for field, missing in [('chunk_id', 'document_evidence_missing'),
                               ('operation_id', 'operation_evidence_missing')]:
            if not any(getattr(link, field) is not None for link in links):
                blockers.append(missing)
        if not any(link.qc_result_id in {q.qc_result_id for q in qc} for link in links):
            blockers.append('qc_event_link_missing')
    result = _base('LC-' + digest([row.observation_id, event.event_id if event else None])[:32],
        observation_id=row.observation_id, station_id=row.station_id,
        physical_sensor_id=row.sensor_id or None, variable_code=row.variable_code,
        event_id=event.event_id if event else None,
        event_start=event.event_start if event else None, event_end=event.event_end if event else None,
        source_flags={'qc_flag': raw.qc_flag if raw else None, 'mqc_flag': raw.mqc_flag if raw else None},
        recheck_flags=[{'qc_result_id': q.qc_result_id, 'flag': q.result_flag,
                        'rule_id': q.qc_rule_id, 'rule_version': q.rule_version}
                       for q in qc[:MAX_OBSERVATIONS]], blockers=sorted(set(blockers)))
    result['status'] = 'NEEDS_EVIDENCE' if blockers else 'DRAFT'
    return result


def _channel_candidates(db, request):
    ids = _ids(request, 'channel_record_ids')
    if not ids:
        return []
    run_id = request.get('registry_run_id')
    if not isinstance(run_id, str) or not run_id:
        raise HTTPException(422, 'registry_run_id is required for channel_record_ids')
    if db.get_bind().dialect.name != 'postgresql':
        raise HTTPException(422, 'Facility review requires the PostgreSQL registry')
    run = db.execute(text("SELECT run_id FROM facility_registry.run WHERE run_id=:r AND manifest->>'status'='PUBLISHED_REVIEW_ONLY'"),
                     {'r': run_id}).first()
    if not run:
        raise HTTPException(404, 'Published facility registry run not found')
    rows = db.execute(text('SELECT * FROM facility_registry.channel_month WHERE run_id=:r AND record_id=ANY(:ids) ORDER BY record_id'),
                      {'r': run_id, 'ids': ids}).mappings().all()
    if len(rows) != len(ids):
        raise HTTPException(404, 'Channel record not found in requested run')
    candidates = []
    for row in rows:
        blockers = ['human_review_required', 'closed_evidence_event_required', 'approved_label_missing']
        if not row['physical_sensor_id']:
            blockers.append('physical_sensor_unresolved')
        if not row['valid_from'] or not row['valid_to']:
            blockers.append('sensor_validity_interval_unresolved')
        candidates.append(_base('LC-' + digest([run_id, row['record_id']])[:32],
            registry_run_id=run_id, channel_record_id=row['record_id'],
            source_hash=digest(dict(row)), station_id=row['station_code'],
            item_code=row['item_code'], physical_sensor_id=row['physical_sensor_id'],
            valid_from=row['valid_from'], valid_to=row['valid_to'],
            coverage_month=row['month'], source_flags=None, recheck_flags=[], blockers=blockers))
    return candidates


def _dataset_review(db, dataset_id):
    dataset = db.get(DatasetRegistry, dataset_id)
    if dataset is None:
        raise HTTPException(404, 'Dataset not found')
    selection = db.query(ObservationStandard).filter(
        ObservationStandard.timestamp_utc >= dataset.period_start,
        ObservationStandard.timestamp_utc < dataset.period_end)
    for field, values in [('station_id', dataset.station_scope), ('sensor_id', dataset.sensor_scope),
                          ('variable_code', dataset.variable_scope)]:
        if values and '*' not in values:
            selection = selection.filter(getattr(ObservationStandard, field).in_(values))
    rows = selection.order_by(ObservationStandard.observation_id).limit(MAX_DATASET_ROWS + 1).all()
    errors = []
    if len(rows) > MAX_DATASET_ROWS:
        errors.append('dataset_review_limit_exceeded')
    # Existing validators dereference event evidence; bound it before calling them.
    event_ids = set()
    if not errors:
        for row in rows:
            links = db.query(EventEvidence).filter_by(observation_id=row.observation_id).limit(MAX_EVIDENCE + 1).all()
            if len(links) > MAX_EVIDENCE:
                errors.append('event_evidence_limit_exceeded')
                break
            event_ids.update(link.event_id for link in links)
            if len(event_ids) > MAX_OBSERVATIONS:
                errors.append('event_review_limit_exceeded')
                break
        for event_id in sorted(event_ids) if not errors else []:
            if db.query(EventEvidence).filter_by(event_id=event_id).limit(MAX_EVIDENCE + 1).count() > MAX_EVIDENCE:
                errors.append('event_evidence_limit_exceeded')
                break
    if not errors:
        # These functions only read; they do not call build/validate/approve endpoints.
        from app.api.routes_datasets import validation_errors
        errors.extend(validation_errors(db, dataset))
        if event_ids:
            duplicates = db.query(DatasetMembership, DatasetRegistry).join(
                DatasetRegistry, DatasetRegistry.dataset_id == DatasetMembership.dataset_id).filter(
                DatasetMembership.event_id.in_(event_ids),
                DatasetRegistry.dataset_id != dataset_id,
                DatasetRegistry.dataset_name == dataset.dataset_name,
                DatasetRegistry.dataset_split != dataset.dataset_split).limit(MAX_EVIDENCE + 1).all()
            errors.extend('event_split_leakage:' + member.event_id + ':' + other.dataset_id
                          for member, other in duplicates[:MAX_EVIDENCE])
            if len(duplicates) > MAX_EVIDENCE:
                errors.append('membership_review_limit_exceeded')
    if dataset.status != 'VALIDATED':
        errors.append('validated_dataset_required_for_promotion')
    return {'dataset_id': dataset_id, 'persisted_status': dataset.status,
            'status': 'NEEDS_EVIDENCE' if errors else 'DRAFT', 'read_only': True,
            'promotion_eligible': not errors, 'human_approval_required': True,
            'training_eligible': False, 'errors': sorted(set(errors)),
            'review_complete': not any('limit_exceeded' in error for error in errors)}


def _prediction_document_review(db, request):
    ids = _ids(request, 'prediction_document_ids')
    if not ids:
        return None
    if not request.get('prediction_at'):
        raise HTTPException(422, 'prediction_at with UTC offset is required')
    try:
        cutoff = utc(request['prediction_at'], require_offset=True)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, 'Invalid prediction_at')
    errors = []
    for chunk_id in ids:
        doc = db.query(DocumentIndex).filter_by(chunk_id=chunk_id).first()
        if doc is None:
            errors.append('document_missing:' + chunk_id)
            continue
        # Document evidence can support a retrospective label. Using that
        # evidence as a prediction feature requires independently recorded availability.
        available = (doc.metadata_json or {}).get('available_at')
        if available is None:
            errors.append('document_availability_unverified:' + chunk_id)
        else:
            try:
                available = utc(available, require_offset=True)
                if available > cutoff:
                    errors.append('future_document_feature:' + chunk_id)
            except (HTTPException, ValueError, TypeError, AttributeError):
                errors.append('document_availability_invalid:' + chunk_id)
        if doc.document_date and utc(doc.document_date) > cutoff:
            errors.append('future_report_date:' + chunk_id)
    return {'prediction_at': cutoff, 'chunk_ids': ids,
            'feature_eligible': not errors, 'errors': sorted(set(errors))}


def propose(db, request, qc_output=None):
    """Return JSON-serializable proposals without flushing or persisting the session.

    Select by event_id, observation_ids, channel_record_ids + registry_run_id,
    and/or dataset_id. Upstream QC output is untrusted context, never a label.
    """
    if hasattr(request, 'model_dump'):
        request = request.model_dump()
    if not isinstance(request, dict):
        raise HTTPException(422, 'Label review request must be an object')
    request = dict(request)
    if isinstance(qc_output, dict) and not request.get('channel_record_ids'):
        interval, audit = qc_output.get('interval_evidence') or {}, qc_output.get('audit') or {}
        if not isinstance(interval, dict) or not isinstance(audit, dict):
            raise HTTPException(422, 'Invalid QC evidence envelope')
        channels = interval.get('channels') or []
        run_id = audit.get('run_id')
        if not isinstance(channels, list) or any(not isinstance(row, dict) for row in channels):
            raise HTTPException(422, 'QC channels must be evidence objects')
        if channels and run_id:
            if len(channels) > MAX_OBSERVATIONS:
                raise HTTPException(422, 'Narrow QC context to at most 100 channels')
            request['channel_record_ids'] = [row.get('record_id') for row in channels]
            request['registry_run_id'] = run_id
    with db.no_autoflush:
        ids = _ids(request, 'observation_ids')
        event = None
        if request.get('event_id'):
            event = db.get(EventRegistry, request['event_id'])
            if event is None:
                raise HTTPException(404, 'Event not found')
            links = db.query(EventEvidence).filter_by(event_id=event.event_id).filter(
                EventEvidence.observation_id.is_not(None)).limit(MAX_OBSERVATIONS + 1).all()
            ids = sorted(set(ids) | {link.observation_id for link in links})
            if len(ids) > MAX_OBSERVATIONS:
                raise HTTPException(422, 'Narrow the review to at most 100 observations')
        candidates = []
        for observation_id in ids:
            row = db.get(ObservationStandard, observation_id)
            if row is None:
                raise HTTPException(404, 'Observation not found: ' + observation_id)
            candidates.append(_observation_candidate(db, row, event))
        candidates.extend(_channel_candidates(db, request))
        if not candidates and qc_output is not None:
            # Parquet samples need not have ORM observation IDs. Preserve this
            # gap explicitly; never invent an observation or physical sensor.
            candidates.append(_base('LC-QC-CONTEXT', observation_id=None,
                physical_sensor_id=None, source_flags=None, recheck_flags=[],
                evidence_origin='UPSTREAM_QC_CONTEXT_UNVERIFIED',
                blockers=['persisted_evidence_selection_required',
                          'physical_sensor_unresolved', 'human_review_required']))
        review = _dataset_review(db, request['dataset_id']) if request.get('dataset_id') else None
        document_review = _prediction_document_review(db, request)
        if review and document_review and document_review['errors']:
            review['errors'] = sorted(set(review['errors'] + document_review['errors']))
            review['promotion_eligible'] = False
            review['status'] = 'NEEDS_EVIDENCE'
        blockers = [] if candidates or review or document_review else ['bounded_evidence_selection_required']
        return jsonable_encoder({'schema_version': 'label-review-agent-1', 'agent': 'label_dataset_registry',
            'status': 'NEEDS_EVIDENCE' if blockers or any(c['blockers'] for c in candidates)
                or (review and review['errors']) or (document_review and document_review['errors']) else 'DRAFT',
            'read_only': True, 'training_eligible': False, 'candidates': candidates,
            'dataset_review': review, 'blockers': blockers,
            'prediction_document_review': document_review,
            'qc_context_received': qc_output is not None,
            'qc_context_policy': 'CONTEXT_ONLY_NOT_HUMAN_LABEL_OR_CAUSE',
            'required_next_step': 'HUMAN_EVIDENCE_REVIEW',
            'approval_endpoint': '/api/approvals/approve',
            'dataset_approval_endpoint': '/api/datasets/{dataset_id}/approve'})
