# 파일 역할: API 응답을 확인하는 개발용 검증 코드입니다.
import urllib.request
import json
try:
    req = urllib.request.Request(
        'http://localhost:8080/api/rag/chat', 
        data=json.dumps({'query': 'DOTT 장비 통신 주기는?'}).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    print(res.read().decode())
except Exception as e:
    if hasattr(e, 'read'):
        print("ERROR BODY:", e.read().decode())
    else:
        print("ERROR:", e)
