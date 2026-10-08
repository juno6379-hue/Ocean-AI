# 파일 역할: 학습 모델 산출물과 재현성 메타데이터를 저장합니다.
"""Local candidate artifacts; writing files never deploys or approves a model."""
import hashlib
import json
from pathlib import Path
import joblib
import sklearn
import numpy as np
import pandas as pd


def save_candidate(model, metadata, evaluation, features, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    artifact = output / "model.joblib"
    joblib.dump(model, artifact)
    # Load only the artifact we just produced, never an untrusted pickle/joblib file.
    restored = joblib.load(artifact)
    np.testing.assert_allclose(restored.predict(features), evaluation.prediction, rtol=1e-12, atol=1e-12)
    metadata = {**metadata, "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "artifact_reload_verified": True, "package_versions": {"sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__}}
    evaluation.to_csv(output / "test_predictions.csv", index_label="timestamp_utc")
    (output / "metrics.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return metadata
