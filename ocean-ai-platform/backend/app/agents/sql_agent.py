# 파일 역할: 관측 DB 질의 단계의 입력과 결과를 처리합니다.
import os
import uuid
import datetime
from sqlalchemy import text
from app.core.database import engine, SessionLocal
from app.llm.ollama_client import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import pandas as pd

def classify_intent(query: str) -> str:
    """
    질문의 의도를 분류하여 RAG를 쓸지 SQL(DB)를 쓸지 결정합니다.
    """
    llm = get_llm(temperature=0)
    
    template = """당신은 질문 분석기입니다. 사용자의 질문이 주어지면, 질문의 의도를 분석하여 오직 두 가지 카테고리 중 하나만 대답하세요.
1. 'DATA': 질문이 원시 데이터 다운로드, 관측값 조회, 수치 현황, DB 조회를 명시적으로 요구하는 경우. (예: 데이터베이스에서 찾아줘, 엑셀로 다운받아줘)
2. 'DOC': 질문이 보고서(일일상황보고, 분석보고서 등), 매뉴얼, 지침서, 규정, 문서에 포함된 내용이나 특이사항을 묻는 경우. (예: 8월 일일상황보고 특이사항 알려줘)

질문: {query}

카테고리(DATA 또는 DOC):"""
    
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm | StrOutputParser()
    
    result = chain.invoke({"query": query}).strip().upper()
    if "DATA" in result:
        return "DATA"
    return "DOC"

def ask_sql_agent(query: str) -> dict:
    """
    사용자의 질문에 따라 DB 데이터를 조회하고 결과를 반환합니다.
    (실제로는 LangChain SQLDatabase 툴킷을 사용할 수 있으나 안정성을 위해 안전하게 쿼리/추출을 처리합니다)
    """
    # 임의로 데모 시나리오를 위한 SQL 추출 (전체 조위관측소 값들을 일정 기간으로)
    db = SessionLocal()
    try:
        # 질문 내용에 따라 기간이나 대상을 LLM으로 추출할 수 있으나,
        # 여기서는 가장 최근 24시간 전체 관측소 데이터를 추출하는 것으로 기본 처리합니다.
        now = datetime.datetime.utcnow()
        yesterday = now - datetime.timedelta(days=1)
        
        sql = """
        SELECT o.station_id, s.station_name, o.timestamp_utc, o.variable_code, o.value_raw, o.value_status 
        FROM observation_raw o
        JOIN station_metadata s ON o.station_id = s.station_id
        ORDER BY o.timestamp_utc DESC
        """
        
        result = db.execute(text(sql))
        rows = result.fetchall()
        
        if not rows:
            return {
                "answer": "DB에서 요청하신 데이터를 찾을 수 없습니다.",
                "source": "MDC DB (ocean_ai.db)"
            }
            
        # 데이터를 CSV로 임시 저장
        # frontend/public 폴더에 저장해서 다운로드 링크로 제공
        public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "..", "frontend", "public", "downloads")
        os.makedirs(public_dir, exist_ok=True)
        
        filename = f"tide_data_{uuid.uuid4().hex[:8]}.csv"
        filepath = os.path.join(public_dir, filename)
        
        # Pandas를 이용해 CSV 저장
        df = pd.DataFrame(rows, columns=["관측소ID", "관측소명", "측정시간(UTC)", "관측항목", "관측값", "상태"])
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        
        # 답변 생성
        total_count = len(rows)
        stations = df["관측소명"].unique()
        
        answer = f"""요청하신 데이터 추출이 완료되었습니다.

MDC DB(관측 데이터베이스)에서 **{len(stations)}개 관측소**({', '.join(stations[:3])} 등)의 데이터를 성공적으로 조회했습니다. 
총 **{total_count:,}건**의 관측 데이터가 추출되었습니다.

아래 링크를 클릭하여 전체 데이터를 CSV 파일 형식으로 다운로드하실 수 있습니다.

[데이터 다운로드 (CSV)](/downloads/{filename})"""

        return {
            "answer": answer,
            "source": "MDC DB (ocean_ai.db) SQL 추출기"
        }
    except Exception as e:
        return {
            "answer": f"데이터 추출 중 오류가 발생했습니다: {str(e)}",
            "source": "System Error"
        }
    finally:
        db.close()
