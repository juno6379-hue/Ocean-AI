# 02. 설치 및 실행 가이드 (Setup and Installation)

새로운 개발 환경이나 운영 서버에 플랫폼을 구축하기 위한 가이드입니다. 
본 프로젝트는 로컬 개발 시 **Windows 환경** 및 **PowerShell**을 기준으로 작성되었습니다.

## 🛠️ 1. 사전 요구 사항 (Prerequisites)

시스템을 구동하기 위해 아래 프로그램들이 설치되어 있어야 합니다.
* **Node.js**: v18.x 이상 (프론트엔드 구동용)
* **Python**: 3.10 이상 (백엔드 구동 및 AI 모델 실행용)
* **Git**: 소스 코드 관리용
* **Ollama**: 로컬 LLM 실행을 위한 필수 플랫폼 ([Ollama 다운로드](https://ollama.com/download))

## 📦 2. 프로젝트 가져오기

```powershell
# Git 저장소 클론 (원격 저장소가 연결된 경우)
git clone https://github.com/juno6379/Develop.git AI_Observation
cd AI_Observation/ocean-ai-platform
```

## 🧠 3. AI 모델 준비 (Ollama)

플랫폼은 추론에 LLM을 사용하며, 텍스트 임베딩 모델은 LangChain을 통해 자동으로 다운로드됩니다. 
가장 먼저 Ollama를 실행하여 사용할 LLM 모델을 설치해 주세요.

```powershell
# 터미널 창을 열고 Llama3 모델(또는 권장 모델) 다운로드
ollama run llama3
# 다운로드가 완료되면 'ctrl+d' 또는 '/bye'로 빠져나옵니다.
```

## ⚙️ 4. 백엔드 (Backend) 설정 및 실행

FastAPI 백엔드를 설정합니다.

```powershell
# 1. 백엔드 디렉토리로 이동
cd backend

# 2. Python 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\activate

# 3. 의존성 패키지 설치
pip install -r requirements.txt

# 4. 데이터베이스 초기화 및 시드 데이터 주입
# (최초 1회만 실행 - SQLite 및 ChromaDB 초기화)
python -m app.scripts.seed_db
python -m app.scripts.seed_part_a

# 5. 백엔드 서버 실행 (포트 8080)
# 테스트 모드로 실행할 경우 환경변수 설정 적용
$env:TEST_MODE="1"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```
> [!TIP]
> 백엔드가 정상 구동되면 `http://localhost:8080/docs` 에서 Swagger API 문서를 확인하실 수 있습니다.

## 🎨 5. 프론트엔드 (Frontend) 설정 및 실행

React 대시보드를 설정합니다. (백엔드를 실행해둔 상태로 새 터미널 창을 열어주세요.)

```powershell
# 1. 프론트엔드 디렉토리로 이동
cd frontend

# 2. NPM 패키지 설치
npm install

# 3. 개발 서버 실행 (포트 5173 기본값)
npm run dev
```

> [!NOTE]
> 프론트엔드가 실행되면 `http://localhost:5173` 링크를 클릭하여 브라우저에서 플랫폼에 접속하실 수 있습니다.

## ⚠️ 문제 해결 (Troubleshooting)

1. **`[Errno 10048] Address already in use` 에러 발생 시**
   * 이미 8080 포트가 사용 중인 경우입니다. `taskkill /F /PID <포트점유PID>` 명령을 통해 기존 백엔드 프로세스를 종료한 뒤 다시 실행하세요.
2. **`HuggingFaceEmbeddings` 경고 메시지**
   * 백엔드 실행 시 LangChain 버전 관련 Deprecation 경고가 뜰 수 있으나, 플랫폼 구동 자체에는 영향을 미치지 않으므로 무시하셔도 무방합니다.
3. **API 응답 지연 (Timeout)**
   * 처음 AI 분석 API를 호출할 때, 모델 로딩으로 인해 다소 시간이 걸릴 수 있습니다. (첫 1회 이후에는 빨라집니다.)
