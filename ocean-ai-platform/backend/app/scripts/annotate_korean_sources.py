# 파일 역할: 개발 소스의 한글 설명 주석을 추가하고 적용 범위를 검증합니다.
"""원본 자료·외부 라이브러리를 제외한 개발 소스에 파일 역할 주석을 적용한다."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXTENSIONS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.html', '.sql', '.ps1', '.sh'}
EXCLUDED = {'.work', '__pycache__', 'data', 'node_modules', 'dist', 'chroma_db', '.pytest_cache'}
SUBJECTS = {
    'agents':'다중 에이전트 업무 흐름', 'ai_insights':'관측 품질 분석 및 추천',
    'alerts':'이상 알림', 'approvals':'사용자 승인 및 검토 이력', 'dashboard':'통합 대시보드 집계',
    'datalake':'대용량 관측자료 저장 및 통계', 'datasets':'학습 데이터셋 버전',
    'equipment':'관측장비 및 운영 이력', 'events':'관측 사건', 'features':'학습 특성 정의와 값',
    'forecasting':'조위 예측', 'imputation':'결측 보간', 'mlops':'모델 학습·평가·배포',
    'models':'모델 등록부', 'observations':'관측 자료 조회', 'qc':'품질관리 및 학습 라벨',
    'rag':'문서 근거 검색', 'reports':'보고서 등록부', 'service_monitoring':'수집 서비스 상태',
    'stations':'관측소 기준정보', 'test_auto':'자동 검증', 'tide_analysis':'조위 분석',
    'automation':'업무 자동화', 'automation_test':'자동 테스트 실행', 'cause_diagnosis':'이상 원인 후보 분석',
    'daily_inspection':'일일 점검', 'data_monitoring':'관측 데이터 감시', 'document_ingester':'문서 수집',
    'human_approval':'사람의 승인', 'qc_copilot':'품질관리 업무지원', 'report':'보고서 초안',
    'tide_residual':'조위 편차 분석', 'rag_knowledge':'문서 근거 기반 답변', 'sql':'관측 DB 질의',
}
DESCRIPTIONS = {
    'document_contract':'임베딩 모델·해시·차원·컬렉션의 공통 계약을 검증합니다.',
    'document_pipeline':'파일 목록·처리 이력·중복 검사와 벡터 및 관계형 색인 적재를 관리합니다.',
    'report_parser':'보고서 형식별 본문·표를 추출하고 절·관측소·이슈 단위로 나눕니다.',
    'hybrid_retriever':'메타데이터와 관계형 조건을 적용해 벡터·키워드 근거를 통합 검색합니다.',
    'semantic_ingestion':'문서 수집 요청을 이력 관리가 가능한 의미 기반 파이프라인으로 전달합니다.',
    'embedder_factory':'설정에 맞는 임베딩 제공자를 선택합니다.',
    'document_loader':'문서 로딩 기능을 위한 확장 위치입니다.',
    'answer_generator':'검색된 근거로 답변을 생성하기 위한 확장 위치입니다.',
    'retriever':'문서 검색 기능을 위한 확장 위치입니다.',
    'state':'에이전트 사이에 전달할 상태와 문맥을 정의합니다.',
    'orchestrator':'에이전트 실행 순서와 상태 전이를 구성합니다.',
    'multi_agent_workflow':'품질 분석·원인 후보·근거 검색·승인 흐름을 연결합니다.',
    'config':'환경변수와 실행 환경 설정을 읽습니다.',
    'database':'관계형 데이터베이스 연결과 요청별 세션을 관리합니다.',
    'security':'서버에 등록된 사용자 인증과 작업 권한을 검사합니다.',
    'ollama_client':'로컬 언어모델 연결과 호출 설정을 제공합니다.',
    'evaluator':'예측 또는 분류 모델의 평가 지표를 계산합니다.',
    'feature_generator':'미래 정보를 사용하지 않는 시계열 학습 특성을 계산합니다.',
    'model_registry':'학습 모델 산출물과 재현성 메타데이터를 저장합니다.',
    'trainer':'시간 순서에 따른 학습·검증과 모델 산출물 생성을 수행합니다.',
    'enums':'품질 상태 등 도메인 공통 코드값을 정의합니다.',
    'add_part_a_apis':'기존 업무지원 API 구성 보조 스크립트입니다.',
    'analyze_long_term':'장기간 관측 시계열의 추세와 통계를 분석합니다.',
    'analyze_parquet':'변환된 Parquet 자료의 분포와 분석 결과를 확인합니다.',
    'build_datalake':'관측 원본을 파티션 Parquet로 변환하고 처리 목록을 기록합니다.',
    'build_imputation_dataset':'긴 결측 보간에 사용할 학습 자료를 구성합니다.',
    'convert_to_parquet':'관측 파일을 Parquet 저장 형식으로 변환합니다.',
    'embed_docs':'기존 문서 임베딩 명령을 새 이력 관리 파이프라인에 연결합니다.',
    'forecast_tide_baseline':'조위 예측의 기준 모델과 결과를 생성합니다.',
    'ingest_document_library':'보고서 목록화·의미 청킹·임베딩 적재 배치를 실행합니다.',
    'inspect_mdc_schema':'MDC 운영 DB의 접근 가능한 테이블과 컬럼을 조사합니다.',
    'inventory_mdc_items':'MDC 관측항목 코드 목록을 조회합니다.',
    'load_datalake_stats':'원시 관측 전체 대신 Data Lake 집계 통계를 DB에 적재합니다.',
    'load_mdc_item_mapping':'관측항목 코드 매핑 기준정보를 DB에 반영합니다.',
    'migrate_document_index':'기존 문서 색인 테이블의 확장 컬럼을 반영합니다.',
    'migrate_mlops_registry':'모델 및 재학습 등록부의 스키마 변경을 반영합니다.',
    'migrate_process_schema':'관측 처리 계층의 스키마와 인덱스를 갱신합니다.',
    'patch_mlops':'기존 모델 운영 코드 수정을 위한 보조 스크립트입니다.',
    'patch_part_a_ui':'기존 업무지원 화면 구성을 위한 보조 스크립트입니다.',
    'profile_spool':'보관 관측 파일의 크기·확장자·표본 구조를 조사합니다.',
    'seed_db':'개발용 초기 데이터베이스 자료를 구성합니다.',
    'seed_db_extended':'개발용 확장 예제 자료를 구성합니다.',
    'seed_features':'초기 학습 특성 정의를 등록합니다.',
    'seed_mlops':'개발용 모델 운영 예제 자료를 구성합니다.',
    'seed_part_a':'개발용 업무지원 예제 자료를 구성합니다.',
    'seed_qc_rules':'초기 품질검사 규칙 정의를 등록합니다.',
    'sync_mdc_db':'MDC 메타데이터·관측자료를 조회해 원시 및 표준화 관측으로 동기화합니다.',
    'test_oracle':'설정된 Oracle 연결의 동작을 확인합니다.',
    'train_mdc_multivariate':'MDC 관측자료 기반 다변량 모델 학습을 실행합니다.',
    'train_parquet_history':'과거 Parquet 시계열을 사용한 모델 학습을 실행합니다.',
    'validate_live_pipeline':'실자료 처리 경로와 연결 상태를 검증합니다.',
    'anomaly_detector':'관측값의 이상 후보를 계산합니다.',
    'long_gap_imputation':'긴 결측 구간과 원본을 분리한 보간 후보를 관리합니다.',
    'pilot_source_parser':'시험 관측 원본의 형식과 필수 필드를 검증합니다.',
    'test_runner':'자동 검증 실행 결과를 모읍니다.',
    'create_sample_data':'개발 및 검증에 사용하는 예제 파일을 생성합니다.',
    'ingest_reports':'기존 보고서 수집 경로를 실행합니다.',
    'seed_data':'개발용 초기 예제 자료를 생성합니다.',
    'rag_initializer':'검색용 초기 자료와 저장소를 준비합니다.',
    'conftest':'테스트를 운영 DB와 분리하고 공통 실행 환경을 설정합니다.',
    'test_document_pipeline':'문서 추출·중복 방지·벡터 연결·검색 근거 회귀를 검증합니다.',
    'test_ml_training':'모델 학습과 평가의 재현성을 검증합니다.',
    'test_pilot_source_parser':'시험 원본 파서의 형식·시간대·오류 처리를 검증합니다.',
    'test_safety_workflow':'권한·승인·데이터셋 및 운영 경로의 회귀를 검증합니다.',
    'test_api':'API 응답을 확인하는 개발용 검증 코드입니다.',
    'test_chatbot':'챗봇 요청과 응답을 확인하는 개발용 검증 코드입니다.',
    'test_rag':'문서 검색과 답변 연결을 확인하는 개발용 검증 코드입니다.',
    'App':'화면 경로와 공통 레이아웃을 구성합니다.',
    'client':'서버 요청에 공통 주소·인증 정보·오류 처리를 적용합니다.',
    'Chatbot':'사용자 질문과 근거 기반 답변을 표시합니다.',
    'Layout':'업무 메뉴와 화면 공통 배치를 제공합니다.',
    'OperatorSession':'작업자 인증 세션과 권한 상태를 표시합니다.',
    'AIInsights':'관측 품질 분석과 추천을 표시합니다.',
    'Alerts':'이상 알림과 사건 상태를 표시합니다.',
    'Dashboard':'관측 및 품질관리 통합 현황을 표시합니다.',
    'DataLake':'대용량 관측자료 변환·통계·분석 단계 현황을 표시합니다.',
    'Equipment':'관측장비 기준정보와 운영 상태를 표시합니다.',
    'Forecasting':'조위 예측 결과와 평가 정보를 표시합니다.',
    'MLOps':'모델·데이터셋 버전과 학습·배포 상태를 표시합니다.',
    'Observations':'관측 현황과 관측소 위치를 표시합니다.',
    'QCCopilot':'품질검사·보간·근거 문서를 활용하는 업무지원 화면입니다.',
    'Reports':'업무 보고서 목록과 처리 상태를 표시합니다.',
    'ServiceMonitoring':'관측자료 수집 서비스의 상태를 표시합니다.',
    'StationProfile':'관측소별 기준정보와 상세 현황을 표시합니다.',
    'System':'시스템 설정과 운영 상태를 표시합니다.',
    'vite.config':'프런트엔드 개발 서버와 빌드 설정을 정의합니다.',
    'annotate_korean_sources':'개발 소스의 한글 설명 주석을 추가하고 적용 범위를 검증합니다.',
}


def source_files():
    files=[]
    for folder in ['backend/app','backend/scripts','backend/tests','frontend/src']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in EXTENSIONS and not (set(p.relative_to(ROOT).parts)&EXCLUDED):files.append(p)
    for folder in [ROOT,ROOT/'backend',ROOT/'frontend']:
        files.extend(p for p in folder.iterdir() if p.is_file() and p.suffix in EXTENSIONS)
    return sorted(set(files))


def description(path, content):
    stem=path.stem
    if not content.strip():return '현재 구현이 비어 있는 확장용 소스 파일입니다.'
    if stem.startswith('routes_'):
        return SUBJECTS.get(stem[7:],stem[7:])+' 관련 요청을 검증하고 API 응답을 제공합니다.'
    if stem.endswith('_agent'):
        return SUBJECTS.get(stem[:-6],stem[:-6])+' 단계의 입력과 결과를 처리합니다.'
    if stem=='domain':
        return '요청·응답 데이터의 필드와 검증 구조를 정의합니다.' if 'schemas' in path.parts else '관측·품질검사·라벨·문서·모델 등의 관계형 저장 구조를 정의합니다.'
    if stem=='main':return '백엔드 API·실행 수명주기·예외 처리를 구성합니다.' if path.suffix=='.py' else '프런트엔드 애플리케이션을 화면에 연결합니다.'
    if stem=='index':return '화면에서 사용하는 백엔드 API 호출 함수를 제공합니다.' if path.suffix=='.ts' else '애플리케이션 진입 화면과 공통 자원을 정의합니다.'
    if path.suffix=='.css':return '애플리케이션 화면의 공통 스타일을 정의합니다.'
    return DESCRIPTIONS.get(stem,stem+' 모듈의 실행 코드와 설정을 관리합니다.')


def apply_comments(apply=False):
    results=[]
    backup=ROOT/'backend/tests/.work/comment_originals'
    for path in source_files():
        raw=path.read_bytes(); bom=raw.startswith(b'\xef\xbb\xbf')
        content=raw.decode('utf-8-sig')
        if '파일 역할:' in '\n'.join(content.splitlines()[:5]):
            results.append({'path':str(path.relative_to(ROOT)),'has_korean_comment':True,'changed':False});continue
        desc=description(path,content)
        prefix='# ' if path.suffix in {'.py','.ps1','.sh'} else '// '
        if path.suffix=='.css':comment='/* 파일 역할: '+desc+' */'
        elif path.suffix=='.html':comment='<!-- 파일 역할: '+desc+' -->'
        elif path.suffix=='.sql':comment='-- 파일 역할: '+desc
        else:comment=prefix+'파일 역할: '+desc
        newline='\r\n' if '\r\n' in content else '\n'
        lines=content.splitlines(keepends=True); position=0
        while position<len(lines) and (lines[position].startswith('#!') or (position<2 and re.search(r'coding[:=]',lines[position]))):position+=1
        lines.insert(position,comment+newline)
        if apply:
            target=backup/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.write_bytes(raw)
            path.write_bytes(('\ufeff' if bom else '').encode('utf-8')+''.join(lines).encode('utf-8'))
        results.append({'path':str(path.relative_to(ROOT)),'has_korean_comment':apply,'changed':apply,'description':desc})
    return results


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--output',type=Path)
    args=ap.parse_args();records=apply_comments(args.apply)
    report={'files':len(records),'missing_comments':sum(not r['has_korean_comment'] for r in records),'records':records}
    if args.output:args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
