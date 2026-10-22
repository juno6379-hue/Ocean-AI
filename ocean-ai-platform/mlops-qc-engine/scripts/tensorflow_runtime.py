"""Select the isolated TensorFlow interpreter without loading TensorFlow."""
from __future__ import annotations

import os
from pathlib import Path


def resolve_tensorflow_python(base: Path) -> Path:
    """Prefer the verified CPU overlay while preserving an explicit diagnostic override."""
    base = Path(base).resolve()
    override = os.environ.get("AI_QC_TF_PYTHON", "").strip()
    if override:
        selected = Path(override).expanduser()
        if not selected.is_absolute():
            selected = base / selected
        selected = selected.resolve()
        if not selected.is_file():
            raise ValueError(f"AI_QC_TF_PYTHON 실행 파일을 찾을 수 없습니다: {selected}")
        return selected
    cpu = base / "runtime/python3_10_cpu_env/Scripts/python.exe"
    if cpu.is_file():
        return cpu
    return base / "runtime/python3_10_env_restored/python.exe"
