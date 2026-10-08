"""Rebuild an exact legacy membership as a new unapproved v2 version.

The review is read-only. Execution requires actual source/protocol authority,
preserves the original snapshot, and never copies legacy approval authority.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from sqlalchemy import select
from app.models.domain import DatasetRegistry
from app.models.evidence import DatasetMembership
from app.models.source_observation_binding import SourceObservationBinding
from app.services.dataset_lineage import build_content, leakage_errors, family_lock
from app.services.source_contract_snapshot import (
    read_bounded, source_roots, dependency_review, freeze_dependencies,
    normalize_utc_fields, protocol_binding_errors, DependencyError, guarded_path,
)
from app.ml.comparison_runner import digest, _atomic_json

LEGACY = 'event-evidence-dataset-1'
CONFIG_FIELDS = ('dataset_name','dataset_split','station_scope','sensor_scope','variable_scope',
                 'period_start','period_end','feature_version','label_version',
                 'preprocessing_version','qc_rule_version')


def _legacy(db, dataset_id, root, expected_sha=None, lock=False):
    query = db.query(DatasetRegistry).filter_by(dataset_id=dataset_id)
    old = (query.with_for_update() if lock else query).first()
    if old is None: raise DependencyError('LEGACY_DATASET_NOT_FOUND')
    if not old.data_hash: raise DependencyError('LEGACY_BUILT_SNAPSHOT_REQUIRED')
    if expected_sha and expected_sha != old.data_hash: raise DependencyError('LEGACY_REFERENCE_CHANGED')
    try:snapshot, raw, sha = read_bounded(Path(root)/(old.data_hash+'.json'), [root], old.data_hash)
    except OSError as exc:raise DependencyError('LEGACY_SNAPSHOT_NOT_READABLE') from exc
    if snapshot.get('schema_version') != LEGACY: raise DependencyError('LEGACY_V1_SNAPSHOT_REQUIRED')
    if snapshot.get('dataset_id') != dataset_id: raise DependencyError('LEGACY_DATASET_IDENTITY_MISMATCH')
    records=snapshot.get('records')
    if not isinstance(records,list) or not 1<=len(records)<=250000 or any(
        not isinstance(r,dict) or not isinstance(r.get('id'),str) or not r['id'] or
        not isinstance(r.get('event_id'),str) or not r['event_id'] or not isinstance(r.get('label'),dict) or
        not isinstance(r['label'].get('label_id'),str) or not r['label']['label_id'] for r in records):
        raise DependencyError('LEGACY_FROZEN_RECORDS_SHAPE_INVALID')
    if len({r['id'] for r in records})!=len(records):raise DependencyError('LEGACY_FROZEN_RECORDS_DUPLICATE_ID')
    return old, snapshot, raw, sha


def review_migration(db, dataset_id, new_dataset_id, new_version, dependencies, root, expected_sha=None):
    old, original, _, sha = _legacy(db,dataset_id,root,expected_sha)
    if not isinstance(new_dataset_id,str) or not 1 <= len(new_dataset_id) <= 128 or new_dataset_id == dataset_id:
        raise DependencyError('NEW_DATASET_ID_REQUIRED')
    if not isinstance(new_version,str) or not new_version or new_version == old.dataset_version:
        raise DependencyError('NEW_DATASET_VERSION_REQUIRED')
    if not isinstance(dependencies,list) or len(dependencies)>128 or any(
        not isinstance(d,dict) or set(d)!={'role','path','sha256'} or
        not isinstance(d['role'],str) or not isinstance(d['path'],str) or not d['path'] or
        not isinstance(d['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',d['sha256']) for d in dependencies):
        raise DependencyError('DEPENDENCY_SPEC_INVALID')
    _, current, counts = build_content(db,old)
    errors = list(current['validation_errors'])
    if digest(current) != sha: errors.append('LEGACY_LIVE_LINEAGE_CHANGED')
    old_members = db.query(DatasetMembership).filter_by(dataset_id=dataset_id).all()
    wanted = {(r['id'],r['label']['label_id'],r['event_id'],sha) for r in original['records']}
    if {(r.observation_id,r.label_id,r.event_id,r.snapshot_hash) for r in old_members} != wanted or len(old_members)!=len(wanted):
        errors.append('LEGACY_FROZEN_MEMBERSHIP_CHANGED')
    if not current['records'] or counts['UNREVIEWED']: errors.append('LEGACY_REVIEWED_MEMBERSHIP_REQUIRED')
    existing=db.get(DatasetRegistry,new_dataset_id)
    if existing or db.query(DatasetRegistry).filter_by(dataset_name=old.dataset_name,dataset_version=new_version).first():
        errors.append('NEW_DATASET_VERSION_ALREADY_EXISTS')
    bodies={};proofs={};bindings=[];seen=set()
    for spec in dependencies:
        role=spec['role']
        if role not in {'SOURCE_CONTRACT','SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY'}:
            errors.append('MIGRATION_APPROVED_DEPENDENCY_ROLE_REQUIRED');continue
        try:
            body,_,actual=read_bounded(spec['path'],source_roots(),spec['sha256'])
            if actual in seen:raise DependencyError('DUPLICATE_DEPENDENCY')
            seen.add(actual)
            authority,issues=dependency_review(db,body,actual,role)
            errors.extend(role+':'+e for e in issues)
            bindings.append({'role':role,'sha256':actual,'approval_receipt':authority})
            if role=='SOURCE_CONTRACT' and authority:
                for oid,proof in body['observations'].items():
                    if oid in proofs:errors.append('AMBIGUOUS_SOURCE_CONTRACT:'+oid)
                    proofs[oid]=(actual,proof)
            elif role!='SOURCE_CONTRACT' and authority:
                if role in bodies:errors.append(role+'_ONE_FROZEN_DEPENDENCY_REQUIRED')
                else:bodies[role]=body
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append(role+':'+getattr(exc,'code','DEPENDENCY_READ_OR_SHAPE_INVALID'))
    if not any(d['role']=='SOURCE_CONTRACT' and d['approval_receipt'] for d in bindings):errors.append('SOURCE_CONTRACT_DEPENDENCIES_MISSING')
    for role in ('SPLIT_PROTOCOL','EVALUATION_PROTOCOL','ACCEPTANCE_POLICY'):
        if role not in bodies:errors.append(role+'_ONE_FROZEN_DEPENDENCY_REQUIRED')
    for record in current['records']:
        oid=record['id'];bound=db.get(SourceObservationBinding,oid);source=proofs.get(oid)
        if not bound or not source or bound.receipt_sha256!=source[0] or bound.payload!=source[1]:
            errors.append('SOURCE_OBSERVATION_BINDING_MISSING_OR_CHANGED:'+oid)
    proposed=normalize_utc_fields(copy.deepcopy(current))
    proposed.update(dataset_id=new_dataset_id,dataset_version=new_version)
    errors.extend(protocol_binding_errors(proposed,bodies))
    errors.extend(leakage_errors(db,old,bodies.get('SPLIT_PROTOCOL')))
    result={'schema_version':'dataset-v1-v2-migration-review-1','status':'BLOCKED' if errors else 'READY_TO_BUILD_NEW_VERSION',
            'approved':False,'mutation_performed':False,'legacy_dataset_id':dataset_id,'legacy_snapshot_sha256':sha,
            'new_dataset_id':new_dataset_id,'new_dataset_version':new_version,'member_count':len(current['records']),
            'member_ids_sha256':digest(sorted(r['id'] for r in current['records'])),
            'dependency_authorities':sorted(bindings,key=lambda d:(d['role'],d['sha256'])),
            'blockers':sorted(set(errors)),
            'next_steps':['Build new version with exact reviewed dependencies','Validate v2','Separate reviewer DATASET approval'],
            'legacy_approval_copied':False,'final_build_revalidation_required':True}
    result['review_sha256']=digest(result)
    return result


def migrate_v2(db,dataset_id,new_dataset_id,new_version,dependencies,root,expected_legacy_sha,expected_review_sha,actor):
    if not actor.user_id or actor.role not in {'operator','reviewer','admin'}:raise DependencyError('AUTHENTICATED_OPERATOR_REQUIRED')
    old,_,original_bytes,_=_legacy(db,dataset_id,root,expected_legacy_sha,True)
    family_lock(db,old.dataset_name)
    review=review_migration(db,dataset_id,new_dataset_id,new_version,dependencies,root,expected_legacy_sha)
    if review['review_sha256']!=expected_review_sha:raise DependencyError('MIGRATION_REVIEW_CHANGED')
    if review['blockers']:raise DependencyError('MIGRATION_REVIEW_BLOCKED:'+','.join(review['blockers']))
    new=DatasetRegistry(dataset_id=new_dataset_id,dataset_version=new_version,created_by=actor.user_id,
                        status='DRAFT',approved_by=None,**{k:copy.deepcopy(getattr(old,k)) for k in CONFIG_FIELDS})
    try:
        db.add(new);db.flush()
        _,snapshot,counts=build_content(db,new)
        snapshot=freeze_dependencies(db,snapshot,dependencies,root)
        snapshot['validation_errors']=sorted(set(snapshot['validation_errors']+leakage_errors(db,new,
            next(b for d in dependencies if d['role']=='SPLIT_PROTOCOL' for b,_,_ in [read_bounded(d['path'],source_roots(),d['sha256'])]))))
        if snapshot['validation_errors'] or counts['UNREVIEWED'] or not snapshot['records']:
            raise DependencyError('MIGRATED_V2_VALIDATION_FAILED:'+','.join(snapshot['validation_errors']))
        if digest(sorted(r['id'] for r in snapshot['records']))!=review['member_ids_sha256']:
            raise DependencyError('MIGRATION_MEMBERSHIP_CHANGED')
        sha=digest(snapshot);path=guarded_path(Path(root)/(sha+'.json'),[root])
        path.parent.mkdir(parents=True,exist_ok=True)
        raw=json.dumps(snapshot,sort_keys=True,ensure_ascii=False,allow_nan=False,default=str).encode('utf-8')
        if path.exists():
            if path.read_bytes()!=raw:raise DependencyError('IMMUTABLE_DATASET_SNAPSHOT_CHANGED')
        else:
            from app.services.source_contract_snapshot import immutable_copy
            immutable_copy(root,sha,raw)
            # Publish the immutable content-addressed dataset file separately
            # from dependency copies; do not overwrite an existing path.
            import os
            try:os.link(Path(root)/'dependencies'/(sha+'.json'),path)
            except FileExistsError:
                if path.read_bytes()!=raw:raise DependencyError('IMMUTABLE_DATASET_SNAPSHOT_CHANGED')
        new.data_hash=sha;new.sample_count=len(snapshot['records'])
        new.normal_count,new.suspect_count,new.bad_count,new.missing_count=counts['1'],counts['3'],counts['4'],counts['9']
        for r in snapshot['records']:
            db.add(DatasetMembership(dataset_id=new_dataset_id,observation_id=r['id'],label_id=r['label']['label_id'],event_id=r['event_id'],snapshot_hash=sha))
        if (Path(root)/(old.data_hash+'.json')).read_bytes()!=original_bytes:raise DependencyError('LEGACY_SNAPSHOT_CHANGED_DURING_MIGRATION')
        new.status='BUILT';db.commit()
        return {'status':'BUILT_UNAPPROVED','dataset_id':new_dataset_id,'data_hash':sha,'member_count':new.sample_count,
                'migration_review_sha256':expected_review_sha,'legacy_dataset_id':dataset_id,
                'legacy_snapshot_sha256':expected_legacy_sha,'legacy_approval_copied':False,'approved':False,
                'next_steps':['Validate v2','Separate reviewer DATASET approval']}
    except Exception:
        db.rollback();raise
