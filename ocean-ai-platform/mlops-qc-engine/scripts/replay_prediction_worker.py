"""One model per process, keeping native TensorFlow memory separate across models."""
import argparse
import ctypes
import faulthandler
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.workspace_paths import resolve_manifest_root
sys.modules.setdefault("replay_prediction_worker", sys.modules[__name__])
sys.modules.setdefault("scripts.replay_prediction_worker", sys.modules[__name__])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--station", required=True)
    parser.add_argument("--sensor", required=True)
    args = parser.parse_args()
    if os.name == "nt":
        # Native errors stay fatal and in stderr; prevent a modal from blocking the controller.
        ctypes.windll.kernel32.SetErrorMode(0x0002)
    faulthandler.enable()
    from scripts import offline_model_suite as suite
    from scripts.local_trial_manifest import validate, write_json
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate(manifest)
    root = resolve_manifest_root(manifest, BASE)
    if args.output.exists() or args.output.resolve().is_relative_to(root):
        raise ValueError("Output must be new and outside protected AI input")
    pair = next(p for p in manifest["models"] if (p["station"], p["sensor"]) == (args.station, args.sensor))
    with suite.np.load(args.input, allow_pickle=False) as inputs:
        raw = inputs["raw_inputs"]
        historical = inputs["historical_predictions"]
        times = inputs["timestamps"].tolist()
    model, scaler, _ = suite.assets(root, pair)
    actual = suite.predict(model, scaler, raw)
    difference = suite.np.abs(actual - historical)
    write_json(args.output, {"timestamps": times, "historical": historical.tolist(),
                             "recomputed": actual.tolist(), "difference": difference.tolist()})


if __name__ == "__main__":
    main()
