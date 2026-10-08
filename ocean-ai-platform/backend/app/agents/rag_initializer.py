# 파일 역할: 검색용 초기 자료와 저장소를 준비합니다.
import os
from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma_db")

def init_chroma_db():
    print("Initializing ChromaDB with sample ocean observation manuals...")
    
    # 1. 문서 준비 (Mock Documents)
    docs = [
        Document(
            page_content="최근 3개월간 후포(LASER) 관측소에서 통신 장애가 4회 발생했습니다. 주된 원인은 해안가 염분으로 인한 모뎀 단자 부식 및 접촉 불량으로 파악되었습니다. 매뉴얼 상 권장 조치 사항은 1) 현장 출동 후 모뎀 리셋, 2) 부식된 단자 교체 및 방청 작업입니다.",
            metadata={"source": "DOC-2025-0012: 후포 관측소 통신장애 이력 보고서"}
        ),
        Document(
            page_content="제주 관측소의 수온 센서 보정은 다음 절차를 따릅니다:\n1. 표준 온도계(기준 장비)를 이용해 주변 해수 온도를 3회 측정합니다.\n2. 측정된 평균값과 센서 데이터의 오차를 계산합니다.\n3. 관측소 시스템 관리자 메뉴에서 '센서 캘리브레이션'을 선택 후 오프셋 값을 입력합니다.",
            metadata={"source": "MANUAL-OP-04: 해양수질 센서 유지보수 및 교정 매뉴얼"}
        ),
        Document(
            page_content="파고 이상탐지 모델의 재학습 권장 기준은 성능 저하(F1 Score 0.85 미만 3일 이상 지속) 또는 데이터 분포의 급격한 변동(Data Drift 30% 이상)이 감지될 때입니다. 해당 조건이 충족되면 시스템이 MLOps 대시보드에 재학습 승인 대기 알림을 띄웁니다.",
            metadata={"source": "TECH-AI-002: 해양관측 AI 모델 운영 가이드"}
        ),
        Document(
            page_content="조위(Tide) 관측 데이터 품질검사(QC) 가이드라인에 따르면, 조위 값이 1시간 동안 50cm 이상 급변하거나, 동일한 값이 6시간 이상 지속(고착)될 경우 품질 등급을 'BAD(불량)' 또는 'SUSPECT(의심)'로 즉시 분류하고 운영자에게 알림을 발송해야 합니다.",
            metadata={"source": "GUIDE-QC-01: 실시간 해양관측 데이터 품질관리 지침"}
        ),
        Document(
            page_content="염분 센서(Salinity Sensor)의 측정값이 비정상적으로 낮게 나올 경우, 가장 흔한 원인은 센서 표면에 해조류나 따개비 등 해양 생물이 부착되었기 때문입니다. 이 경우 잠수부를 동원하여 센서 표면을 부드러운 솔로 청소하고, 방오 도료(Anti-fouling) 상태를 점검해야 합니다.",
            metadata={"source": "MANUAL-OP-05: 염분 센서 청소 및 생물부착 방지 매뉴얼"}
        )
    ]
    
    # 2. 임베딩 모델 로드 (HuggingFace 한국어 모델)
    print("Loading HuggingFace Embedding Model (jhgan/ko-sroberta-multitask)...")
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
    
    # 3. ChromaDB 생성 및 저장
    os.makedirs(os.path.dirname(CHROMA_DB_DIR), exist_ok=True)
    print(f"Creating vector store at {CHROMA_DB_DIR}...")
    vectorstore = Chroma.from_documents(
        documents=docs, 
        embedding=embeddings, 
        persist_directory=CHROMA_DB_DIR
    )
    print("ChromaDB initialization complete!")
    return vectorstore

if __name__ == "__main__":
    init_chroma_db()
