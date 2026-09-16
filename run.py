#!/usr/bin/env python3
"""One command, from a bare clone to a validated predictions.csv.

    python run.py

Checks the inputs, builds the ranking, and runs the official
validate_submission.py over the result. Exit code 0 means the file would be
accepted by the grader; any other exit code has already said what is wrong.

If the dependencies in requirements.txt are not importable, this creates a
local .venv, installs the pinned versions into it, and re-runs itself there,
so a reviewer needs nothing but a Python interpreter and the data folder.
Pass --no-venv to use the interpreter you are already in.

Nothing on the path from data/ to predictions.csv touches the network.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
VENV_DIR = HERE / ".venv"
REQUIREMENTS = HERE / "requirements.txt"

# Import name -> what to say if it is missing. pytest is in requirements.txt
# for the test suite but is not needed to produce predictions.csv.
RUNTIME_MODULES = ["pandas", "numpy", "pyarrow"]

# Set when we re-exec inside .venv, so a broken install cannot loop forever.
BOOTSTRAP_FLAG = "LPDG_BOOTSTRAPPED"


def missing_modules() -> list[str]:
    return [m for m in RUNTIME_MODULES if importlib.util.find_spec(m) is None]


def venv_python() -> pathlib.Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def bootstrap_into_venv(argv: list[str]) -> int:
    """Create .venv, install the pinned requirements, and re-run there."""
    python = venv_python()
    if not python.exists():
        print(f"creating {VENV_DIR.name} (dependencies are not installed here)...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    print("installing pinned requirements...")
    subprocess.check_call(
        [str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "-r", str(REQUIREMENTS)]
    )
    env = dict(os.environ, **{BOOTSTRAP_FLAG: "1"})
    return subprocess.call([str(python), str(pathlib.Path(__file__).resolve()), *argv], env=env)


def check_data(data_dir: pathlib.Path) -> str | None:
    """Return a human-readable problem with the data folder, or None."""
    if not data_dir.exists():
        return (
            f"no data folder at {data_dir}.\n"
            "  The 105 MB dataset is not shipped with this repository (it is not ours to\n"
            "  publish). Unzip the provided 03-challenge-data.zip so that its 'data' folder\n"
            "  sits at the repository root, or pass --data /path/to/data."
        )
    expected = ["telemetry", "meter_read_success.csv", "gateway_master.csv"]
    absent = [name for name in expected if not (data_dir / name).exists()]
    if absent:
        return f"{data_dir} is missing: {', '.join(absent)}"
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=pathlib.Path, default=HERE / "data")
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "predictions.csv")
    parser.add_argument("--no-venv", action="store_true",
                        help="use the current interpreter even if dependencies are missing")
    parser.add_argument("--auto-window", action="store_true",
                        help="score the most recent 8 weeks in the data rather than the "
                             "fixed submission window (use after adding a new month)")
    args = parser.parse_args(argv)

    absent = missing_modules()
    if absent and not args.no_venv and not os.environ.get(BOOTSTRAP_FLAG):
        print(f"missing dependencies: {', '.join(absent)}")
        return bootstrap_into_venv(argv)
    if absent:
        print(f"missing dependencies: {', '.join(absent)}\n"
              f"  run: {sys.executable} -m pip install -r requirements.txt", file=sys.stderr)
        return 1

    problem = check_data(args.data)
    if problem:
        print(f"cannot run: {problem}", file=sys.stderr)
        return 1

    # Imported here, not at module scope, so the bootstrap above can run in an
    # interpreter that does not have pandas yet.
    sys.path.insert(0, str(HERE))
    from src.predict import main as predict_main
    from validate_submission import main as validate_main

    predict_argv = ["--data", str(args.data), "--out", str(args.out)]
    if args.auto_window:
        predict_argv.append("--auto-window")
    code = predict_main(predict_argv)
    if code != 0:
        return code

    if args.auto_window:
        # validate_submission.py hard-codes the eight submission Mondays, so it
        # cannot pass on a window that deliberately is not those weeks. Skipping
        # it here rather than reporting a failure that is not one.
        print(f"wrote {args.out} for a rolling window; skipping validate_submission.py, "
              "which only checks the fixed 2026-02-02..2026-03-23 submission window.")
        return 0
    return validate_main([str(args.out)])


if __name__ == "__main__":
    raise SystemExit(main())
