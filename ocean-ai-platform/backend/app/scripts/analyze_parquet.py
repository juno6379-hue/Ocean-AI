# 파일 역할: 변환된 Parquet 자료의 분포와 분석 결과를 확인합니다.
import pandas as pd
import sys

def analyze_heterogeneity(file_path):
    print(f"=== Parquet 데이터 이질성 및 품질 분석 보고서 ===")
    print(f"분석 대상 파일: {file_path}")

    try:
        df = pd.read_parquet(file_path)
    except Exception as e:
        print(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return

    # 1. 기본 정보
    print("\n[1. 기본 데이터 볼륨]")
    print(f"총 레코드(행) 수: {len(df):,}")
    print(f"컬럼 목록: {list(df.columns)}")

    # 2. 시간(관측 시기) 해상도 및 이질성 분석
    print("\n[2. 시간(Time) 관측주기 이질성 분석]")
    if 'Time' in df.columns:
        df['Time'] = pd.to_datetime(df['Time'])
        df = df.sort_values('Time')

        start_time = df['Time'].min()
        end_time = df['Time'].max()
        print(f"관측 기간: {start_time} ~ {end_time}")

        # 관측 주기(Time Delta) 분석
        time_diffs = df['Time'].diff().dropna()
        mode_diff = time_diffs.mode()

        if not mode_diff.empty:
            print(f"가장 빈번한 관측 주기(최빈값): {mode_diff[0]}")

        # 주기가 일정하지 않은(이질적인) 경우 비율 확인
        if not mode_diff.empty:
            irregular_ratio = (time_diffs != mode_diff[0]).mean() * 100
            print(f"불규칙한 관측 주기(통신 단절 등 이빨 빠짐) 비율: {irregular_ratio:.2f}%")
    else:
        print("Time 컬럼이 존재하지 않습니다.")

    # 3. 결측치 분석
    print("\n[3. 결측치(Missing Values) 발생률]")
    total_rows = len(df)
    for col in df.columns:
        null_count = df[col].isnull().sum()
        null_ratio = (null_count / total_rows) * 100
        print(f" - {col}: {null_count:,}건 결측 ({null_ratio:.2f}%)")

    # 4. 품질 상태 플래그(QC) 분포
    print("\n[4. 품질 제어(QC) 플래그 분포]")
    qc_cols = [col for col in df.columns if 'QC' in col.upper()]
    for col in qc_cols:
        print(f"\n[{col} 플래그 종류 및 빈도]")
        qc_counts = df[col].value_counts(dropna=False)
        for flag, count in qc_counts.items():
            ratio = (count / total_rows) * 100
            print(f" - {flag if pd.notna(flag) else 'NaN'}: {count:,}건 ({ratio:.2f}%)")

if __name__ == "__main__":
    file_path = r"C:\AI_Observation\ocean-ai-platform\data_lake\tide_obs\DT_0001.parquet"
    analyze_heterogeneity(file_path)
