# 파일 역할: 관측 파일을 Parquet 저장 형식으로 변환합니다.
import os
import time
import pandas as pd

def main():
    source_file = r"E:\백업\data\old\spool(2001_2021)\DT_0001-인천조위관측소-부표식(OTT)조위.txt"
    target_dir = r"C:\AI_Observation\ocean-ai-platform\data_lake\tide_obs"
    target_file = os.path.join(target_dir, "DT_0001.parquet")

    # Create target directory
    os.makedirs(target_dir, exist_ok=True)

    print(f"[{time.strftime('%H:%M:%S')}] 변환 시작...")
    print(f"원본 파일: {source_file}")
    
    # Check original file size
    orig_size = os.path.getsize(source_file)
    print(f"원본 파일 크기: {orig_size / (1024*1024):.2f} MB")

    start_time = time.time()
    
    # Read CSV using fast arrow backend if possible, or standard C engine
    print("CSV 읽는 중 (이 작업은 메모리와 시간이 소요될 수 있습니다)...")
    try:
        # The file header is: Time,OTT,QC1,QC2
        # Try reading with pyarrow engine for speed
        df = pd.read_csv(source_file, engine='pyarrow')
    except Exception as e:
        print(f"Pyarrow 엔진 오류, 기본 엔진 사용: {e}")
        df = pd.read_csv(source_file)

    read_time = time.time()
    print(f"읽기 완료! (총 {len(df):,} 줄, 소요 시간: {read_time - start_time:.2f}초)")

    print(f"[{time.strftime('%H:%M:%S')}] Parquet 형식으로 압축 저장 중...")
    
    # Save as parquet (snappy compression is default)
    df.to_parquet(target_file, engine='pyarrow', compression='snappy')
    
    write_time = time.time()
    
    # Check new file size
    new_size = os.path.getsize(target_file)
    
    print(f"저장 완료! (소요 시간: {write_time - read_time:.2f}초)")
    print(f"대상 파일: {target_file}")
    print(f"새 파일 크기: {new_size / (1024*1024):.2f} MB")
    
    # Compression ratio
    compression_ratio = (orig_size - new_size) / orig_size * 100
    print(f"\n✅ 요약: 파일 크기가 {compression_ratio:.1f}% 감소했습니다! ({orig_size/(1024*1024):.2f}MB -> {new_size/(1024*1024):.2f}MB)")

if __name__ == "__main__":
    main()
