"""서로 다른 원천 보존 스키마를 명시적 family manifest로 선택한다."""
from pathlib import Path,PurePosixPath
import json
from app.services.lake_manifest import checksum,LakeManifestError

def select_raw_family(root,manifest_path,expected_format):
    root=Path(root).resolve();rel=PurePosixPath(manifest_path)
    if rel.is_absolute() or '..' in rel.parts or '\\' in manifest_path or ':' in manifest_path:
        raise LakeManifestError('UNSAFE_MANIFEST_PATH')
    manifest=(root/manifest_path).resolve()
    if not manifest.is_relative_to(root/'metadata'):raise LakeManifestError('MANIFEST_OUTSIDE_METADATA')
    data=json.loads(manifest.read_text(encoding='utf8'))
    allowed={'oracle_string_snapshot':'RAW_SNAPSHOT_COMPLETE','sqlplus_string_records':'RAW_PARSED_RECONCILED','positional_csv_strings':'RAW_CSV_STRINGS_COMPLETE'}
    if expected_format not in allowed:raise LakeManifestError('UNSUPPORTED_SOURCE_FORMAT')
    if data.get('status')!=allowed[expected_format]:raise LakeManifestError('SOURCE_FAMILY_NOT_RECONCILED')
    if expected_format=='oracle_string_snapshot' and not data.get('columns'):raise LakeManifestError('ORACLE_SCHEMA_REQUIRED')
    if expected_format in ['sqlplus_string_records','positional_csv_strings'] and not data.get('source_sha256'):raise LakeManifestError('SOURCE_HASH_REQUIRED')
    selected=[];seen=set();total=0
    import pyarrow.parquet as pq
    for entry in data['files']:
        rel=PurePosixPath(entry['path'])
        if rel.is_absolute() or '..' in rel.parts or rel.parts[0]!='raw' or ':' in entry['path'] or '\\' in entry['path']:raise LakeManifestError('UNSAFE_RAW_PATH')
        path=(root/entry['path']).resolve()
        if not path.is_relative_to(root/'raw') or str(path).casefold() in seen:raise LakeManifestError('RAW_PATH_ESCAPE_OR_DUPLICATE')
        seen.add(str(path).casefold())
        if checksum(path)!=entry['sha256']:raise LakeManifestError('FILE_HASH_MISMATCH')
        pf=pq.ParquetFile(path)
        if pf.metadata.num_rows!=entry['rows']:raise LakeManifestError('ROW_COUNT_MISMATCH')
        layer=(pf.schema_arrow.metadata or {}).get(b'layer')
        expected={'oracle_string_snapshot':b'RAW_DB_SNAPSHOT_NOT_STANDARDIZED','sqlplus_string_records':b'RAW_SQLPLUS_NOT_STANDARDIZED','positional_csv_strings':b'RAW_POSITIONAL_CSV_NOT_STANDARDIZED'}[expected_format]
        if layer!=expected:raise LakeManifestError('SOURCE_FORMAT_MISMATCH')
        selected.append((path,entry['rows']));total+=entry['rows']
    if total!=data.get('parsed_rows' if expected_format=='sqlplus_string_records' else 'rows'):raise LakeManifestError('TOTAL_ROWS_MISMATCH')
    return selected
