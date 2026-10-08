# 파일 역할: 검색용 초기 자료와 저장소를 준비합니다.
import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import shutil

# 1. 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "app", "data")
CHROMA_DB_DIR = os.path.join(DATA_DIR, "chroma_db")
DOCS_DIR = os.path.join(DATA_DIR, "docs")
DUMMY_MANUAL_PATH = os.path.join(DOCS_DIR, "dummy_manual.txt")

OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "jhgan/ko-sroberta-multitask")

def init_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    # 기존 DB 삭제 (초기화)
    if os.path.exists(CHROMA_DB_DIR):
        print(f"Deleting existing ChromaDB at {CHROMA_DB_DIR}...")
        shutil.rmtree(CHROMA_DB_DIR)

def create_dummy_manual():
    dummy_text = """해양관측망 유지보수 지침서 (버전 1.2)

1. DOTT 장비 통신 주기
- DOTT 관측소의 기본 통신 주기는 1시간(60분)입니다. 단, 기상 특보 발효 시 30분 단위로 단축될 수 있습니다.
- 통신이 3회 이상 연속 실패할 경우, 장비는 절전 모드로 진입하며 이후 일 1회 상태 신호만 송신합니다.
- 조치 방법: 현장 방문 후 통신 모듈 재부팅 및 안테나 결속 상태 확인.

2. LASER 조위계 배터리 저전압 경고
- LASER 장비의 배터리 잔량이 20% 미만으로 떨어지면 저전압 경고(DANGER)가 발생합니다.
- 배터리는 통상적으로 6개월마다 교체하는 것이 원칙이나, 일조량이 적은 겨울철에는 태양광 충전 효율 저하로 4개월 주기로 단축될 수 있습니다.
- 조치 방법: 현장 방문하여 예비 배터리 팩으로 교체 후 태양광 패널 표면 이물질(조류 배설물 등) 제거.

3. MIROS 파고계 센서 고착 현상
- 영흥도, 가덕도 등 MIROS 장비에서 종종 센서 고착 알림이 발생합니다.
- 원인: 렌즈 표면에 염분이 누적되거나 습기로 인해 측정이 방해받는 경우.
- 조치 방법: 소프트웨어 리셋 수행. 해결되지 않을 경우 현장 출동하여 렌즈 전용 세척액으로 표면 청소.

4. 연안정지 관측망 품질 검사(QC) 플래그 규정
- 플래그 1: 정상 (수용 가능한 범위 내의 데이터)
- 플래그 2: 주의 (오차 범위 경계에 있으나 활용 가능)
- 플래그 3: 점검 필요 (센서 오프셋 의심)
- 플래그 4: 불량 (물리적 한계를 초과한 데이터, 자동 필터링됨)
"""
    with open(DUMMY_MANUAL_PATH, "w", encoding="utf-8") as f:
        f.write(dummy_text)
    print(f"Dummy manual created at {DUMMY_MANUAL_PATH}")

def initialize_chroma_db():
    print("Loading documents...")
    loader = TextLoader(DUMMY_MANUAL_PATH, encoding="utf-8")
    documents = loader.load()

    print("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)
    
    print(f"Loading Embedding Model ({OLLAMA_EMBED_MODEL})...")
    embeddings = HuggingFaceEmbeddings(model_name=OLLAMA_EMBED_MODEL)

    print(f"Initializing ChromaDB and embedding {len(chunks)} chunks...")
    db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_DB_DIR)
    
    print("ChromaDB initialization complete!")

if __name__ == "__main__":
    init_directories()
    create_dummy_manual()
    initialize_chroma_db()
