# 파일 역할: 문서 벡터 저장소를 단일 Chroma 서버로 실행해 배치와 검색의 동시 접근을 처리합니다.
"""프로젝트 루트에서 PYTHONPATH=backend로 실행한다."""
import sys

from app.rag.document_contract import CHROMA_DIR
from app.core.config import settings


if __name__ == "__main__":
    from chromadb.cli.cli import app

    # 기본 주소는 로컬 전용이다. 외부 공개는 별도의 인증·네트워크 설정이 필요하다.
    sys.argv = ["chroma", "run", "--path", str(CHROMA_DIR),
                "--host", settings.DOCUMENT_CHROMA_HOST,
                "--port", str(settings.DOCUMENT_CHROMA_PORT)]
    app()
