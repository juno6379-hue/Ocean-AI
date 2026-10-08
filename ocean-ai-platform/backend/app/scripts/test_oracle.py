# 파일 역할: 설정된 Oracle 연결의 동작을 확인합니다.
"""Explicit, read-only Oracle smoke check using server-side connection settings."""
from app.scripts.sync_mdc_db import init_oracle, fetch_oracle_data


def check_oracle_connection():
    init_oracle()
    rows = fetch_oracle_data("SELECT 1 AS CONNECTION_OK FROM DUAL")
    if rows != [{"connection_ok": 1}]:
        raise RuntimeError("Oracle read-only smoke check failed")
    return {"connected": True, "read_only": True}


if __name__ == "__main__":
    import json
    print(json.dumps(check_oracle_connection()))
