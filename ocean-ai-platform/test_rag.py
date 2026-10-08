# 파일 역할: 문서 검색과 답변 연결을 확인하는 개발용 검증 코드입니다.
import requests

try:
    res = requests.post(
        'http://localhost:8080/api/rag/chat', 
        json={'query': '2023년 백서에 따르면, 국가해양관측망의 2023년 주요 목적과 내용이 무엇인가요?'},
        timeout=180
    )
    print("Status Code:", res.status_code)
    print("Response:")
    print(res.json())
except Exception as e:
    print("Error:", e)
