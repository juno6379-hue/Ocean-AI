# 파일 역할: 개발용 업무지원 예제 자료를 구성합니다.
import sys
import os
import datetime
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import SessionLocal, engine
from app.models.domain import Base, QCFlagHistory, AIReport

def seed_part_a_data():
    db = SessionLocal()
    
    # 생성되지 않은 테이블(AIReport) 자동 생성
    Base.metadata.create_all(bind=engine)
    
    now = datetime.datetime.now()

    # 1. Seed Reports (if none exist)
    if db.query(AIReport).count() == 0:
        reports = [
            AIReport(
                report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
                title="5월 4주차 서해안(인천, 목포) 조위 이상치 종합 보고서",
                summary="이번 주 서해안 관측소에서 탐지된 조위 데이터 이상치 발생 빈도 및 자동 보정(QC) 결과를 요약한 보고서입니다.",
                created_at=now - datetime.timedelta(days=1),
                status="발행완료",
                author="시스템(AI)",
                report_type="주간 종합 분석"
            ),
            AIReport(
                report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
                title="동해안(후포) 레이저 조위계 이상 패턴 분석 및 교정 제안",
                summary="후포 관측소의 최근 3일간 조위 데이터에서 반복적으로 관찰되는 스파이크 노이즈 패턴의 원인 분석 및 교정 제안입니다.",
                created_at=now - datetime.timedelta(days=3),
                status="승인대기",
                author="김민수 연구원",
                report_type="이상 징후 분석"
            ),
            AIReport(
                report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
                title="남해권 HF-Radar 표층해수유동 예측 정확도 모니터링",
                summary="최근 HF-Radar 관측망의 유속 벡터 오차율 및 AI 모델의 예측 정확도 변동 추이 모니터링 결과입니다.",
                created_at=now - datetime.timedelta(days=5),
                status="발행완료",
                author="시스템(AI)",
                report_type="정기 리포트"
            ),
            AIReport(
                report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
                title="태풍 '볼라벤' 북상에 따른 제주 해상 부이 파고 급증 경고",
                summary="제주 남부 해역 부이에서 관측된 유의파고의 급격한 상승 패턴과 AI 예측 결과를 기반으로 한 사전 경고 리포트입니다.",
                created_at=now - datetime.timedelta(days=10),
                status="발행완료",
                author="시스템(AI)",
                report_type="긴급 알림"
            )
        ]
        db.add_all(reports)
        print(f"Added {len(reports)} AI reports.")

    # 2. Seed QC Flag History (Alerts)
    if db.query(QCFlagHistory).count() == 0:
        alerts = [
            QCFlagHistory(
                observation_id=1,
                flag_type="Spike_Anomaly",
                previous_flag="OK",
                new_flag="ANOMALY",
                reason="조위 데이터에서 임계값(30cm)을 초과하는 급격한 스파이크 노이즈 탐지됨.",
                applied_by="AI_Model_v2.3",
                applied_at=now - datetime.timedelta(minutes=15)
            ),
            QCFlagHistory(
                observation_id=2,
                flag_type="Missing_Value_Imputed",
                previous_flag="MISSING",
                new_flag="OK",
                reason="2시간 동안의 통신 단절로 인한 결측 구간(12건)을 AI가 자동 보간 처리함.",
                applied_by="AI_Model_v2.3",
                applied_at=now - datetime.timedelta(hours=2)
            ),
            QCFlagHistory(
                observation_id=3,
                flag_type="Sensor_Drift",
                previous_flag="OK",
                new_flag="WARNING",
                reason="수온 센서 데이터에서 점진적인 드리프트 현상(-0.5도/일) 감지. 센서 교체 권장.",
                applied_by="AI_Model_v1.8",
                applied_at=now - datetime.timedelta(hours=5)
            ),
            QCFlagHistory(
                observation_id=4,
                flag_type="Out_of_Bounds",
                previous_flag="OK",
                new_flag="ANOMALY",
                reason="동해 부이 파고 데이터가 정상 범위를 벗어남 (관측치: 8.5m, 예측 상한: 6.0m)",
                applied_by="AI_Model_v0.9",
                applied_at=now - datetime.timedelta(days=1)
            ),
            QCFlagHistory(
                observation_id=5,
                flag_type="Consistency_Check",
                previous_flag="OK",
                new_flag="WARNING",
                reason="인접 관측소(목포, 군산)와의 조위 변화 추세 불일치 발생 (상관지수 < 0.8)",
                applied_by="AI_Model_v2.3",
                applied_at=now - datetime.timedelta(days=2)
            )
        ]
        db.add_all(alerts)
        print(f"Added {len(alerts)} QC alerts.")

    db.commit()
    db.close()
    print("Part A Seed data insertion complete.")

if __name__ == "__main__":
    seed_part_a_data()
