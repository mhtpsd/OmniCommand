"""
processing/benchmark_cudf_vs_pandas.py
----------------------------------------
Produces a self-measured CPU-vs-GPU timing comparison for the pitch deck,
instead of quoting NVIDIA's marketing numbers.

RUN THIS SEPARATELY FROM THE LIVE PIPELINE. The live demo only streams
~1000 rows -- nowhere near large enough to show a GPU speedup (transfer
overhead would make it slower, not faster). This script generates its
own large synthetic dataset instead, so it's self-contained.

WHERE TO RUN
A machine or notebook with an NVIDIA GPU. The easiest free option: a
Google Colab notebook with the T4 GPU runtime -- RAPIDS cudf.pandas comes
preinstalled there, so this script works with zero extra setup.

USAGE
    python benchmark_cudf_vs_pandas.py

This orchestrates both timing runs for you, each in its own subprocess
(cudf.pandas.install() is a global monkeypatch on pandas that can't be
cleanly undone in a single process, so CPU and GPU passes must be
isolated from each other -- see the --engine flag below).

    python benchmark_cudf_vs_pandas.py --engine cpu   # CPU-only pass
    python benchmark_cudf_vs_pandas.py --engine gpu   # GPU-accelerated pass (needs RAPIDS)

Take a screenshot of the final comparison for the pitch deck / demo video.
"""

import argparse
import subprocess
import sys
import time

import numpy as np

N_ROWS = 10_000_000
N_ZONES = 50


def _build_dataframe(pd):
    """Synthetic dataset mimicking the real sensor schema, at a scale
    that actually stresses the CPU."""
    rng = np.random.default_rng(seed=42)
    return pd.DataFrame({
        "pipe_section": rng.choice([f"Zone-{i}" for i in range(N_ZONES)], N_ROWS),
        "pressure": rng.normal(5.5, 1.2, N_ROWS),
        "flow_rate": rng.normal(12.0, 3.0, N_ROWS),
        "temperature": rng.normal(22.0, 4.0, N_ROWS),
        "burst_status": rng.choice([0, 1], N_ROWS, p=[0.98, 0.02]),
        "anomaly_score": rng.uniform(0, 1, N_ROWS),
    })


def _time_groupby(pd, label: str) -> float:
    df = _build_dataframe(pd)
    start = time.time()
    df.groupby("pipe_section").agg(
        {"pressure": "mean", "flow_rate": "mean",
         "burst_status": "sum", "anomaly_score": "mean"}
    )
    elapsed = time.time() - start
    print(f"RESULT[{label}] rows={N_ROWS} seconds={elapsed:.4f}")
    return elapsed


def _run_cpu_only() -> None:
    import pandas as pd
    _time_groupby(pd, "cpu")


def _run_gpu_accelerated() -> None:
    try:
        import cudf.pandas
        cudf.pandas.install()
    except ImportError:
        print("cudf not available -- run this on a machine/notebook with "
              "RAPIDS installed (e.g. a free Google Colab T4 runtime).")
        sys.exit(1)
    import pandas as pd
    _time_groupby(pd, "gpu")


def _parse_seconds(output: str, label: str) -> float | None:
    prefix = f"RESULT[{label}]"
    for line in output.splitlines():
        if line.startswith(prefix):
            for part in line.split():
                if part.startswith("seconds="):
                    return float(part.split("=", 1)[1])
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        choices=["cpu", "gpu"],
        default=None,
        help="Run only this engine's timing in the current process "
             "(used internally when orchestrating both as subprocesses).",
    )
    args = parser.parse_args()

    if args.engine == "cpu":
        _run_cpu_only()
        return
    if args.engine == "gpu":
        _run_gpu_accelerated()
        return

    # No --engine given: orchestrate both passes, each in its own
    # subprocess for clean isolation (see module docstring).
    print(f"Generating a {N_ROWS:,}-row synthetic dataset and timing "
          f"groupby+agg, CPU vs GPU...\n")

    print("--- CPU (plain pandas) ---")
    cpu_proc = subprocess.run(
        [sys.executable, __file__, "--engine", "cpu"], capture_output=True, text=True
    )
    print(cpu_proc.stdout, end="")
    if cpu_proc.returncode != 0:
        print(cpu_proc.stderr)
        sys.exit(1)
    cpu_seconds = _parse_seconds(cpu_proc.stdout, "cpu")

    print("\n--- GPU (cudf.pandas) ---")
    gpu_proc = subprocess.run(
        [sys.executable, __file__, "--engine", "gpu"], capture_output=True, text=True
    )
    print(gpu_proc.stdout, end="")
    if gpu_proc.returncode != 0:
        print(gpu_proc.stderr)
        print("\nGPU pass unavailable -- run this script on a CUDA/RAPIDS "
              "machine (e.g. Google Colab T4 runtime) to get the comparison.")
        sys.exit(1)
    gpu_seconds = _parse_seconds(gpu_proc.stdout, "gpu")

    print("\n=== Summary (screenshot this for the pitch deck) ===")
    print(f"CPU (pandas):  {cpu_seconds:.1f}s")
    print(f"GPU (cudf):    {gpu_seconds:.1f}s")
    if gpu_seconds:
        print(f"Speedup:       {cpu_seconds / gpu_seconds:.1f}x")


if __name__ == "__main__":
    main()
