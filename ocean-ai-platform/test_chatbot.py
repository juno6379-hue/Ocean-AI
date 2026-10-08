# 파일 역할: 챗봇 요청과 응답을 확인하는 개발용 검증 코드입니다.
import requests
import json
import time

API_URL = "http://localhost:8080/api/rag/chat"

test_queries = [
    {"query": "조위 관측 데이터 품질검사 기준이 어떻게 돼?", "expected_intent": "DOC"},
    {"query": "MDC DB에서 전체 조위관측소 데이터 추출해줘", "expected_intent": "DATA"},
    {"query": "수온 센서 보정은 어떤 절차로 진행하나요?", "expected_intent": "DOC"},
    {"query": "파고 이상탐지 모델의 재학습 권장 기준을 알려주세요.", "expected_intent": "DOC"},
    {"query": "최근 한달치 데이터를 CSV로 다운로드 하고 싶어", "expected_intent": "DATA"}
]

def run_tests():
    print("=========================================")
    print("   Ocean AI 챗봇 통합 테스트 (QA Suite)  ")
    print("=========================================\n")
    
    passed = 0
    
    for i, tq in enumerate(test_queries):
        print(f"Test {i+1}: '{tq['query']}'")
        try:
            start = time.time()
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    resp = requests.post(API_URL, json={"query": tq["query"]}, timeout=60)
                    break
                except requests.exceptions.ConnectionError:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                    else:
                        raise
            elapsed = time.time() - start
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "")
                source = data.get("source", "")
                
                # 의도 검증 로직 (간단히 source나 answer의 내용으로 판별)
                if "CSV" in answer or "다운로드" in answer or "SQL" in source:
                    detected_intent = "DATA"
                elif "시스템 오류" in answer:
                    detected_intent = "ERROR"
                else:
                    detected_intent = "DOC"
                
                success = (detected_intent == tq["expected_intent"])
                if success:
                    passed += 1
                    status = "\033[92mPASS\033[0m"
                else:
                    status = f"\033[91mFAIL (Expected: {tq['expected_intent']}, Got: {detected_intent})\033[0m"
                
                print(f"[{status}] 소요시간: {elapsed:.1f}s | Source: {source}")
                print(f"답변 요약: {answer[:60]}...\n")
            else:
                print(f"[\033[91mFAIL\033[0m] HTTP Error {resp.status_code}\n")
        except Exception as e:
            print(f"[\033[91mFAIL\033[0m] Exception: {e}\n")
            
    print("=========================================")
    print(f"테스트 결과: {passed} / {len(test_queries)} 통과")
    print("=========================================")

if __name__ == "__main__":
    run_tests()
