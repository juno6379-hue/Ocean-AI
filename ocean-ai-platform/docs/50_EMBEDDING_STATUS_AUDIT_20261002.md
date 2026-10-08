# 임베딩 저장 현황 확인

점검일: 2026-10-02. 기존 Chroma SQLite를 읽기 전용으로 조회하고 활성 PostgreSQL의 document_index를 조회했다. 신규 임베딩은 실행하지 않았다.

## 실측 결과

| 저장소 | 컬렉션/테이블 | 청크/행 수 | 고유 source 수 |
|---|---|---:|---:|
| backend/app/data/chroma_db | ocean_reports | 1,786 | 178 |
| backend/app/data/chroma_db | langchain | 4 | 1 |
| backend/chroma_db | ocean_reports_prod | 0 | 0 |
| 활성 PostgreSQL | document_index | 0 | 0 |

ocean_reports는 1,024차원 컬렉션이며 벡터 인덱스 파일도 존재한다. 등록된 178개 source 경로는 모두 로컬에 존재한다. 확인한 source 예시는 비정형데이터/001_국가해양관측망_일일상황보고 하위 PDF다. langchain은 768차원 컬렉션이며 4개 청크 모두 backend/app/data/docs/dummy_manual.txt를 source로 사용한다.

따라서 실제 자료의 일부 임베딩은 저장되어 있다. 전체 로컬 자료 및 Google Drive 전체 자료의 임베딩 완료로 볼 수 없다. source별 중복 청크 검사와 실제 질의 검색 평가는 이번 확인에 포함하지 않았다.

## 구현과 저장 결과의 차이

- embed_docs.py는 일일상황보고 폴더의 PDF/TXT/DOCX를 읽고 RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)로 분할해 ocean_reports에 저장한다. 이는 문자 수 기준 분할이며 요청한 업무 의미·절 기반 파이프라인과 다르다.
- semantic_ingestion.py에는 의미·절 기반 처리 및 DocumentIndex 저장 코드가 있으나 활성 DB의 해당 테이블은 0건이다. 해당 파이프라인의 운영 적재 완료 근거가 없다.
- rag_knowledge_agent.py는 ocean_reports를 지정한다. hybrid_retriever.py와 semantic_ingestion.py의 Chroma 초기화는 collection_name을 지정하지 않아 기본 langchain 컬렉션을 사용한다. 따라서 현재 실제 보고서 컬렉션과 Hybrid Retrieval 대상이 불일치한다.
- 코드상 get_embedder의 기본 모델은 Ollama mxbai-embed-large다. 저장 데이터에서 생성 당시 모델·버전을 확인하지 못했으므로 실제 생성 모델을 기본 설정만으로 확정하지 않는다.

## 남은 작업

1. 실제 보고서 임베딩과 DocumentIndex를 chunk_id로 연결하고 검색 컬렉션·모델·차원을 일치시킨다.
2. 대상 파일 목록, 처리 성공·실패·제외 사유 및 모델·청킹 버전을 기록한다.
3. 업무 의미·절 기반 청킹으로 요청한 자료군을 처리하고 전체 대상 대비 완료율을 산출한다.
4. 문서명·날짜·section·page·chunk·similarity를 포함하는 실제 검색 검증을 수행한다.
