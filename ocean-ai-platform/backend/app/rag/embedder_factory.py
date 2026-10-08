# 파일 역할: 설정에 맞는 임베딩 제공자를 선택합니다.
import os
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
# from langchain_openai import OpenAIEmbeddings # Will be used when switching to OpenAI

def get_embedder() -> Embeddings:
    """
    Factory function to get the embedding model.
    Currently defaults to Ollama (local open-source), but can easily be swapped 
    to OpenAI or others via environment variables.
    """
    embedder_type = os.getenv("EMBEDDER_TYPE", "ollama").lower()

    if embedder_type == "openai":
        # return OpenAIEmbeddings(model="text-embedding-3-small")
        raise NotImplementedError("OpenAIEmbeddings requires the langchain-openai package and an API key.")
    elif embedder_type == "ollama":
        # Assuming Ollama is running locally and 'mxbai-embed-large' or 'llama3' is pulled.
        # Ensure you have pulled an embedding model in ollama (e.g., `ollama pull mxbai-embed-large`)
        model_name = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")
        return OllamaEmbeddings(model=model_name)
    else:
        raise ValueError(f"Unsupported EMBEDDER_TYPE: {embedder_type}")
