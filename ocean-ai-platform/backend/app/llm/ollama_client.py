# 파일 역할: 로컬 언어모델 연결과 호출 설정을 제공합니다.
import os
import requests
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

# 환경변수 로드 (기본값 설정)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "jhgan/ko-sroberta-multitask")

class MockOllama(BaseChatModel):
    """
    Ollama 서버가 다운되었거나 모델이 없을 때 Fallback으로 동작하는 Mock LLM.
    단순히 미리 정의된 문구를 반환합니다.
    """
    
    @property
    def _llm_type(self) -> str:
        return "mock_ollama"
        
    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        mock_response = "[Mock LLM 응답: Ollama 서버에 연결할 수 없어 임시 응답을 반환합니다. 로컬 LLM 서버 상태를 확인해 주세요.]\n\n- 이 응답은 시스템 자동화에 의해 생성된 더미 텍스트입니다."
        message = AIMessage(content=mock_response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

def is_ollama_running(url: str, model: str) -> bool:
    """Ollama 서버 구동 및 특정 모델 보유 여부를 체크합니다."""
    try:
        res = requests.get(f"{url}/api/tags", timeout=2)
        if res.status_code == 200:
            models = res.json().get("models", [])
            for m in models:
                if m.get("name", "").startswith(model):
                    return True
            print(f"WARNING: Ollama is running, but model '{model}' not found.")
            return False
        return False
    except Exception as e:
        print(f"WARNING: Could not connect to Ollama at {url}: {e}")
        return False

def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """
    Orchestrator나 각 Agent(RAG, QC Copilot, Report)에서 호출하는 
    로컬 LLM 클라이언트 추상화 팩토리.
    """
    if is_ollama_running(OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL):
        return ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_CHAT_MODEL,
            temperature=temperature
        )
    else:
        # Fallback to Mock LLM
        return MockOllama()
