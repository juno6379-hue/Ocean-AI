"""Package immutable fitted files for the nonoperational development server."""
import argparse,copy,json,os
from pathlib import Path
from app.services.raw_next_row_training import canonical,digest,hash_file,immutable,RawTrainingError


def publish(training_root,release_root):
    training_root=Path(training_root).resolve();release_root=Path(release_root).resolve()
    original=json.loads((training_root/'release.json').read_bytes())
    if original.get('schema_version')!='raw-forecast-release-v1' or original.get('approved') is not False or original.get('production_eligible') is not False:
        raise RawTrainingError('FROZEN_DEVELOPMENT_TRAINING_RELEASE_REQUIRED')
    manifest=copy.deepcopy(original);manifest.pop('release_id')
    manifest['source_table']=manifest['source_group']
    manifest['parent_training_release_sha256']=hash_file(training_root/'release.json')
    manifest['publication_scope']='DEVELOPMENT_LOOPBACK_ONLY_NO_PRODUCTION_AUTHORITY'
    for spec in manifest['models']:
        variable=spec['variable_code']
        for key,sha_key in [('artifact_relative_path','artifact_sha256'),('source_membership_relative_path','source_membership_sha256'),('policy_relative_path','policy_sha256')]:
            source=training_root/spec[key];target=release_root/spec[key];target.parent.mkdir(parents=True,exist_ok=True)
            if hash_file(source)!=spec[sha_key]:raise RawTrainingError('PARENT_TRAINING_FILE_CHANGED')
            if target.exists():
                if hash_file(target)!=spec[sha_key]:raise RawTrainingError('PUBLISHED_IMMUTABLE_FILE_CHANGED')
            else:os.link(source,target)
        for kind,old_key,old_sha_key in [('training','training_receipt_relative_path','training_receipt_sha256'),('eval','evaluation_receipt_relative_path','evaluation_receipt_sha256')]:
            source=training_root/spec[old_key]
            if hash_file(source)!=spec[old_sha_key]:raise RawTrainingError('PARENT_FIT_RECEIPT_CHANGED')
            body=json.loads(source.read_bytes());body['parent_fit_receipt_sha256']=spec[old_sha_key]
            body.update(validation_metrics=spec['validation_metrics'],test_metrics=spec['test_metrics'],split_counts=spec['split_counts'],
                        membership_split_counts=spec['membership_split_counts'],source_membership_count=spec['source_membership_count'])
            relative='receipts/'+variable+'-'+kind+'.json';sha=immutable(release_root/relative,canonical(body))
            spec[kind+'_receipt_relative_path']=relative;spec[kind+'_receipt_sha256']=sha
            if kind=='eval':spec['evaluation_receipt_relative_path']=relative;spec['evaluation_receipt_sha256']=sha
        spec['last_values']=spec['last_values3'];spec['last_native_times']=spec['last_native_times3']
    immutable(release_root/'source-selection.json',(training_root/'source-selection.json').read_bytes())
    manifest['release_id']=digest(manifest)
    sha=immutable(release_root/'release-manifest.json',canonical(manifest))
    return {'release_directory':str(release_root),'release_id':manifest['release_id'],'release_manifest_sha256':sha,
            'model_count':len(manifest['models']),'approved':False,'nonoperational':True,'production_eligible':False}


def republish(parent_release_root,release_root):
    """Repackage unchanged fit bytes under a pinned dependency-contract revision."""
    parent=Path(parent_release_root).resolve();target_root=Path(release_root).resolve()
    if target_root==parent or target_root.is_relative_to(parent):
        raise RawTrainingError('NEW_RELEASE_DIRECTORY_REQUIRED')
    parent_bytes=(parent/'release-manifest.json').read_bytes();original=json.loads(parent_bytes)
    if (not isinstance(original,dict) or original.get('schema_version')!='raw-forecast-release-v1'
        or any(original.get(k) is not v for k,v in [('approved',False),('production_eligible',False),('nonoperational',True),('experimental',True)])):
        raise RawTrainingError('FROZEN_DEVELOPMENT_TRAINING_RELEASE_REQUIRED')
    manifest=copy.deepcopy(original);old_id=manifest.pop('release_id',None)
    if old_id!=digest(manifest):raise RawTrainingError('PARENT_RELEASE_ID_CHANGED')
    files={}
    def pin(relative,sha):
        if not isinstance(relative,str) or not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            raise RawTrainingError('PARENT_DEPENDENCY_DESCRIPTOR_INVALID')
        path=Path(relative)
        if path.is_absolute() or path.drive or '..' in path.parts:
            raise RawTrainingError('PARENT_DEPENDENCY_PATH_INVALID')
        source=(parent/path).resolve()
        if not source.is_relative_to(parent) or not source.is_file() or hash_file(source)!=sha:
            raise RawTrainingError('PARENT_TRAINING_FILE_CHANGED')
        if relative in files and files[relative]!=sha:raise RawTrainingError('PARENT_DEPENDENCY_HASH_CONFLICT')
        files[relative]=sha
    pin(manifest.get('source_selection_relative_path'),manifest.get('source_selection_sha256'))
    models=manifest.get('models')
    if not isinstance(models,list) or not models:raise RawTrainingError('PARENT_MODELS_REQUIRED')
    for spec in models:
        if not isinstance(spec,dict):raise RawTrainingError('PARENT_MODEL_DESCRIPTOR_INVALID')
        for key,sha_key in [('artifact_relative_path','artifact_sha256'),('source_membership_relative_path','source_membership_sha256'),
                            ('policy_relative_path','policy_sha256'),('training_receipt_relative_path','training_receipt_sha256'),
                            ('eval_receipt_relative_path','eval_receipt_sha256')]:
            pin(spec.get(key),spec.get(sha_key))
    # Validate every parent dependency before creating any release output.
    for relative,sha in files.items():
        output=target_root/relative;output.parent.mkdir(parents=True,exist_ok=True)
        if output.exists():
            if hash_file(output)!=sha:raise RawTrainingError('PUBLISHED_IMMUTABLE_FILE_CHANGED')
        else:os.link(parent/relative,output)
    manifest.update(parent_release_id=old_id,parent_release_manifest_sha256=hash_file(parent/'release-manifest.json'),
                    publication_revision=2,dependency_contract_version=2,
                    pinned_dependencies=[{'path':path,'sha256':sha} for path,sha in sorted(files.items())])
    manifest['release_id']=digest(manifest)
    sha=immutable(target_root/'release-manifest.json',canonical(manifest))
    return {'release_directory':str(target_root),'release_id':manifest['release_id'],'release_manifest_sha256':sha,
            'model_count':len(models),'dependency_contract_version':2,'unchanged_fitted_files':True,
            'approved':False,'nonoperational':True,'production_eligible':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parents=parser.add_mutually_exclusive_group(required=True)
    parents.add_argument('--training-root');parents.add_argument('--parent-release-root');parser.add_argument('--release-root',required=True)
    args=parser.parse_args()
    result=republish(args.parent_release_root,args.release_root) if args.parent_release_root else publish(args.training_root,args.release_root)
    print(json.dumps(result,ensure_ascii=False))
