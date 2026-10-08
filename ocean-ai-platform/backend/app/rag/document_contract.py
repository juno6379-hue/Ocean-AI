# 파일 역할: 임베딩 모델·해시·차원·컬렉션의 공통 계약을 검증합니다.
"""One persisted embedding contract for ingestion, Hybrid Retrieval and chat."""
import hashlib
import json
import os
import urllib.request
import urllib.error
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(os.getenv("OCEAN_APP_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data")))
STATE_DIR = Path(os.getenv("DOCUMENT_PIPELINE_DIR", str(DATA_DIR / "document_pipeline")))
CHROMA_DIR = DATA_DIR / "chroma_db"
CONTRACT_PATH = STATE_DIR / "contract.json"
PARSER_VERSION = "report-parser-2.2"
CHUNK_VERSION = "section-issue-table-2.1"


def request_json(path, payload=None):
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode('utf-8',errors='replace')[:500]
        raise RuntimeError(f'Ollama HTTP {exc.code}: {detail}') from exc


def load_contract():
    if not CONTRACT_PATH.exists():
        raise RuntimeError("Document embedding contract is not initialized; run ingest_document_library")
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def initialize_contract():
    if CONTRACT_PATH.exists():
        contract = load_contract()
        verify_model(contract)
        if contract['parser_version']==PARSER_VERSION and contract['chunk_version']==CHUNK_VERSION:
            return contract
        (STATE_DIR / ('contract-'+contract['embedding_version']+'.json')).write_text(
            json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    model = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large:latest")
    if ":" not in model:
        model += ":latest"
    models = request_json("/api/tags")["models"]
    found = next((m for m in models if m["name"] == model), None)
    if not found:
        raise RuntimeError(f"Embedding model is not installed: {model}")
    vector = request_json("/api/embed", {"model": model, "input": ["해양 관측 품질관리"], "truncate": False})["embeddings"][0]
    contract = {"provider": "ollama", "model": model, "model_digest": found["digest"],
                "dimension": len(vector), "metric": "cosine", "parser_version": PARSER_VERSION,
                "chunk_version": CHUNK_VERSION, "query_prefix": "Represent this sentence for searching relevant passages: "}
    version = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()[:16]
    contract.update(embedding_version=version, collection="ocean_semantic_" + version)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = CONTRACT_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(CONTRACT_PATH)
    return contract


def verify_model(contract):
    found = next((m for m in request_json("/api/tags")["models"] if m["name"] == contract["model"]), None)
    if not found or found["digest"] != contract["model_digest"]:
        raise RuntimeError("Embedding model digest changed; a new versioned collection is required")


def embed(texts, contract, query=False):
    if query:
        verify_model(contract)
        texts = [contract["query_prefix"] + t for t in texts]
    vectors = request_json("/api/embed", {"model": contract["model"], "input": texts, "truncate": False})["embeddings"]
    if len(vectors) != len(texts) or any(len(v) != contract["dimension"] for v in vectors):
        raise RuntimeError("Embedding response count/dimension does not match the contract")
    return vectors


@lru_cache(maxsize=1)
def chroma_client():
    import chromadb
    from chromadb.config import Settings
    from app.core.config import settings
    # 파일 저장소는 전용 서버 하나만 연다. 배치와 API가 각자 열면 색인 캐시가 어긋날 수 있다.
    return chromadb.HttpClient(
        host=settings.DOCUMENT_CHROMA_HOST,
        port=settings.DOCUMENT_CHROMA_PORT,
        ssl=settings.DOCUMENT_CHROMA_SSL,
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(contract, create=False):
    client = chroma_client()
    if create:
        collection = client.get_or_create_collection(name=contract["collection"], embedding_function=None,
            metadata={"hnsw:space": "cosine", "embedding_version": contract["embedding_version"],
                      "model": contract["model"], "dimension": contract["dimension"]})
    else:
        collection = client.get_collection(contract["collection"], embedding_function=None)
    metadata = collection.metadata or {}
    if metadata.get("embedding_version") != contract["embedding_version"] or metadata.get("dimension") != contract["dimension"]:
        raise RuntimeError("Vector collection contract mismatch")
    return collection
