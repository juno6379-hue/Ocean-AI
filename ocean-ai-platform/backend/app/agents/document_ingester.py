# 파일 역할: document_ingester 모듈의 실행 코드와 설정을 관리합니다.
import os
import glob
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from app.llm.ollama_client import OLLAMA_EMBED_MODEL
from langchain_community.embeddings import HuggingFaceEmbeddings

CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma_db")
DOWNLOAD_DIR = r"C:\AI_Observation\ocean-ai-platform\분류\비정형데이터"

def ingest_documents(max_files=None):
    print(f"Target Directory: {DOWNLOAD_DIR}")
    
    # 1. 모든 PDF 파일 검색
    pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, "**", "*.pdf"), recursive=True)
    
    if not pdf_files:
        print("No PDF files found in the directory.")
        return
        
    print(f"Found {len(pdf_files)} PDF files in total.")
    
    # 파일 생성/수정 시간 기준으로 정렬 (최신 파일이 앞에 오도록)
    pdf_files.sort(key=os.path.getmtime, reverse=True)
    
    if max_files is not None:
        target_files = pdf_files[:max_files]
    else:
        target_files = pdf_files
    
    print(f"\n--- Selected {len(target_files)} files for ingestion ---")
    for f in target_files:
        print(f)
    print("--------------------------------------------------\n")
    
    # 2. 임베딩 모델 로드
    print(f"Loading Embedding Model ({OLLAMA_EMBED_MODEL})...")
    embeddings = HuggingFaceEmbeddings(model_name=OLLAMA_EMBED_MODEL)
    
    # 3. 문서 청킹(Chunking) 설정
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    all_chunks = []
    
    # 4. 파일별 텍스트 추출 및 청킹
    for pdf_path in target_files:
        print(f"Processing: {os.path.basename(pdf_path)}...")
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        print(f"  -> Extracted {len(pages)} pages.")
        
        chunks = text_splitter.split_documents(pages)
        print(f"  -> Split into {len(chunks)} chunks.")
        
        # 메타데이터에 파일명 명시
        for chunk in chunks:
            chunk.metadata["source"] = os.path.basename(pdf_path)
            
        all_chunks.extend(chunks)
        
    if not all_chunks:
        print("No text could be extracted.")
        return
        
    # 5. ChromaDB 에 주입
    print(f"\nAdding {len(all_chunks)} total chunks to ChromaDB at {CHROMA_DB_DIR}...")
    
    # ChromaDB 초기화
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embeddings
    )
    
    # max batch size 제한(5461) 우회를 위해 4000개 단위로 잘라서 주입
    BATCH_SIZE = 4000
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i:i + BATCH_SIZE]
        print(f"  -> Adding batch {i//BATCH_SIZE + 1} ({len(batch)} chunks)...")
        vectorstore.add_documents(batch)
        
    print("Ingestion completed successfully!")

if __name__ == "__main__":
    # 전체 파일 주입
    ingest_documents(max_files=None)
