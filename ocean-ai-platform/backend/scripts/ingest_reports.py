# 파일 역할: 기존 보고서 수집 경로를 실행합니다.
import os
import glob
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import PyPDF2
from datetime import datetime

# Initialize ChromaDB
db_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "chroma_db")
client = chromadb.PersistentClient(path=db_path)

# Determine collection based on environment
is_test = os.environ.get("TEST_MODE", "0") == "1"
collection_name = "ocean_reports_test" if is_test else "ocean_reports_prod"

print(f"[{datetime.now()}] Ingesting reports into collection: {collection_name}")
collection = client.get_or_create_collection(name=collection_name)

reports_dir = r"C:\AI_Observation\ocean-ai-platform\분류\비정형데이터"

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except:
            with open(file_path, "r", encoding="cp949") as f:
                text = f.read()
    elif ext == ".pdf":
        try:
            reader = PyPDF2.PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except:
            pass
    return text

def chunk_and_extract_metadata(text, category, filename):
    # Mocking advanced chunking strategy based on category
    # In a real scenario, this would use LLM or RegEx to parse specific tables and blocks.
    chunks = []
    
    # Simple paragraph chunking
    raw_chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 30]
    
    for i, rc in enumerate(raw_chunks):
        # Default metadata
        meta = {
            "document_type": category,
            "report_date": datetime.now().strftime("%Y-%m-%d"),
            "period_start": datetime.now().strftime("%Y-%m-%d"),
            "period_end": datetime.now().strftime("%Y-%m-%d"),
            "station_id": "UNKNOWN",
            "station_name": "UNKNOWN",
            "variable_code": "ALL",
            "issue_type": "UNKNOWN",
            "risk_level": "NORMAL",
            "source_file": filename,
            "chunk_id": f"{filename}_chunk_{i}"
        }
        
        # Apply specific rules based on category name matching
        if "일일상황보고" in category:
            meta["station_name"] = "전체"
        elif "바다누리" in category:
            meta["issue_type"] = "SERVICE_DELAY"
        elif "대조기" in category:
            meta["risk_level"] = "WARNING"
        elif "주간조위" in category:
            meta["variable_code"] = "TIDE"
        elif "품질처리" in category:
            meta["issue_type"] = "QC_ISSUE"
        elif "일일점검" in category:
            meta["issue_type"] = "EQUIPMENT_ISSUE"
            
        chunks.append({"text": rc, "meta": meta, "id": meta["chunk_id"]})
        
    return chunks

documents = []
metadatas = []
ids = []

cat_limit = 5

if os.path.exists(reports_dir):
    for folder in os.listdir(reports_dir):
        folder_path = os.path.join(reports_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        
        print(f"Processing category: {folder}")
        count = 0
        for root, _, files in os.walk(folder_path):
            for file in files:
                if count >= cat_limit:
                    break
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file_path)[1].lower()
                if ext in [".txt", ".pdf"]:
                    content = extract_text(file_path)
                    if content and len(content.strip()) > 10:
                        chunks = chunk_and_extract_metadata(content, folder, file)
                        for c in chunks:
                            documents.append(c["text"])
                            metadatas.append(c["meta"])
                            ids.append(c["id"])
                        count += 1
            if count >= cat_limit:
                break

if documents:
    # Add in batches to avoid chromadb errors
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        collection.add(
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )
    print(f"[{datetime.now()}] Successfully indexed {len(documents)} chunks.")
else:
    print(f"[{datetime.now()}] No documents to index.")
