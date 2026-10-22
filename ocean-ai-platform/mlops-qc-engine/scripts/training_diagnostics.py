"""Persist small, flushed diagnostics before TensorFlow enters native code."""
from __future__ import annotations

import contextlib
import ctypes
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

np: Any = importlib.import_module("numpy")
_DIAG_LOCK = threading.RLock()


def _is_retryable_permission_error(error: OSError) -> bool:
    return isinstance(error, PermissionError) or getattr(error, "winerror", None) in {5, 32, 33}


ENVIRONMENT_KEYS = (
    "CUDA_VISIBLE_DEVICES", "TF_ENABLE_ONEDNN_OPTS", "TF_DETERMINISTIC_OPS",
    "TF_NUM_INTEROP_THREADS", "TF_NUM_INTRAOP_THREADS", "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
)


def _memory_usage() -> dict:
    if os.name != "nt":
        return {"available": False, "reason": "Windows process counters are unavailable on this platform"}

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return {"available": False, "error": str(ctypes.WinError(ctypes.get_last_error()))}
    return {
        "available": True,
        "working_set_bytes": int(counters.WorkingSetSize),
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        "private_commit_bytes": int(counters.PagefileUsage),
    }


def runtime_diagnostics() -> dict:
    """Read package metadata without importing or initializing TensorFlow."""
    packages: dict[str, str | None] = {}
    for name in ("tensorflow", "tensorflow-intel", "tensorflow-cpu", "keras", "numpy", "scipy", "scikit-learn", "protobuf"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    gpu_driver_modules = {}
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        gpu_driver_modules = {name: bool(kernel32.GetModuleHandleW(name)) for name in ("nvcuda.dll", "nvcuda64.dll", "nvdxgdmal64.dll")}
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count(),
        "packages": packages,
        "environment": {key: os.environ[key] for key in ENVIRONMENT_KEYS if key in os.environ},
        "memory": _memory_usage(),
        "gpu_driver_modules": gpu_driver_modules,
    }


def validate_training_arrays(arrays: dict) -> dict:
    """Reject malformed native inputs and describe the exact arrays passed to fit."""
    required = ("x_train", "y_train", "x_validation", "y_validation")
    result = {}
    for name in required:
        if name not in arrays:
            raise ValueError(f"{name}: 학습 입력 배열이 없습니다.")
        array = arrays[name]
        expected_shape = (4, 2) if name.startswith("x_") else (1,)
        if not isinstance(array, np.ndarray) or tuple(array.shape[1:]) != expected_shape or array.ndim != len(expected_shape) + 1:
            raise ValueError(f"{name}: 입력 배열 shape가 (N, {', '.join(map(str, expected_shape))})와 일치해야 합니다.")
        if array.dtype != np.float32:
            raise ValueError(f"{name}: dtype은 float32여야 합니다.")
        if not array.flags.c_contiguous:
            raise ValueError(f"{name}: 연속된 C 순서 배열이어야 합니다.")
        if array.shape[0] == 0 or not np.isfinite(array).all():
            raise ValueError(f"{name}: 비어 있거나 NaN/무한대가 포함된 배열입니다.")
        result[name] = {
            "shape": list(array.shape), "dtype": str(array.dtype),
            "c_contiguous": bool(array.flags.c_contiguous), "nbytes": int(array.nbytes),
            "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
            "minimum": float(array.min()), "maximum": float(array.max()),
        }
    for suffix in ("train", "validation"):
        if arrays[f"x_{suffix}"].shape[0] != arrays[f"y_{suffix}"].shape[0]:
            raise ValueError(f"y_{suffix}: x_{suffix}와 표본 수가 다릅니다.")
    return result


def record_training_stage(run_folder: Path, stage: str, **details: Any) -> None:
    """Atomically save the last completed boundary and emit one flushed JSON line."""
    run_folder = Path(run_folder)
    run_folder.mkdir(parents=True, exist_ok=True)
    target = run_folder / "training_diagnostics.json"
    payload: dict[str, Any] = {}
    if target.is_file():
        for attempt in range(16):
            try:
                with _DIAG_LOCK:
                    payload = json.loads(target.read_text(encoding="utf-8"))
                break
            except OSError as error:
                if not _is_retryable_permission_error(error) or attempt == 15:
                    raise
                time.sleep(0.05)
    else:
        payload = {
            "schema_version": "candidate-training-diagnostics-1",
            "runtime": runtime_diagnostics(), "events": [],
        }
    event = {
        "stage": stage, "at": datetime.now(timezone.utc).isoformat(),
        "memory": _memory_usage(), **details,
    }
    payload["events"].append(event)
    payload["last_stage"] = stage
    tid = threading.get_ident()
    temporary = target.with_name(f"{target.name}.part.{tid}.{uuid.uuid4().hex[:8]}")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        with _DIAG_LOCK:
            temporary.write_text(serialized, encoding="utf-8")
        for attempt in range(16):
            try:
                with _DIAG_LOCK:
                    temporary.replace(target)
                break
            except OSError as error:
                if not _is_retryable_permission_error(error) or attempt == 15:
                    raise
                time.sleep(0.05)
    finally:
        with contextlib.suppress(OSError):
            temporary.unlink(missing_ok=True)
    print(json.dumps({"stage": stage, "at": event["at"]}, ensure_ascii=False), flush=True)
