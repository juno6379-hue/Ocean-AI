# 파일 역할: 긴 결측 구간과 원본을 분리한 보간 후보를 관리합니다.
"""Long-gap imputation model registry and safe execution boundary.

Deep models are trained offline; this module exposes the approved candidates and
prevents accidental replacement of source observations during training.
"""
MODEL_CANDIDATES = {
    "GRU-D": {"supports": "irregular_sampling,masks", "status": "CANDIDATE"},
    "BRITS": {"supports": "bidirectional_missingness", "status": "CANDIDATE"},
    "SAITS": {"supports": "multivariate_attention", "status": "CANDIDATE"},
}

def plan_long_gap_training(variable_code: str, gap_count: int):
    return {"variable_code": variable_code.upper(), "gap_count": gap_count, "candidates": MODEL_CANDIDATES, "training_status": "QUEUED", "approval_required": True}
