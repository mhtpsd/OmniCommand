"""
validate_risk_formula.py
-------------------------
Validates the new (label-free) risk formula against held-out CSV data.

Run from the project root:
    py analytics-engine/processing/validate_risk_formula.py

IMPORTANT: with only 10 burst rows out of 1000, precision/recall numbers
will be noisy by design. The point is to show they are non-trivial (i.e.
the formula has real signal) without overfitting to the labels.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import csv
import random

# ── Formula parameters (must match risk_scoring.py) ──────────────────────────
PRESSURE_DROP_THRESHOLD = 2.25   # bar
FLOW_SPIKE_THRESHOLD    = 160.0 # L/s
HIGH_RISK_THRESHOLD     = 60.0  # score >= this is flagged "high/critical"

def score_row(pressure: float, flow: float) -> float:
    pressure_drop = max(0.0, PRESSURE_DROP_THRESHOLD - pressure)
    flow_spike    = max(0.0, flow - FLOW_SPIKE_THRESHOLD)
    return min(100.0, max(0.0, pressure_drop * 40 + flow_spike * 3))

# ── Load CSV ──────────────────────────────────────────────────────────────────
csv_path = os.path.join(os.path.dirname(__file__), "../../data/water_leak_detection_1000_rows.csv")

rows = []
with open(csv_path, newline="") as f:
    for r in csv.DictReader(f):
        rows.append({
            "pressure":     float(r["Pressure (bar)"]),
            "flow":         float(r["Flow Rate (L/s)"]),
            "burst_status": int(r["Burst Status"]),
        })

# ── 80/20 split (fixed seed for reproducibility) ─────────────────────────────
random.seed(42)
random.shuffle(rows)
split = int(len(rows) * 0.8)
test_rows = rows[split:]

print(f"Test set: {len(test_rows)} rows")
burst_count = sum(r["burst_status"] for r in test_rows)
print(f"  of which {burst_count} are burst events (ground truth positives)")
print()

# ── Score every test row ──────────────────────────────────────────────────────
tp = fp = fn = tn = 0
for r in test_rows:
    s = score_row(r["pressure"], r["flow"])
    flagged = s >= HIGH_RISK_THRESHOLD
    actual  = r["burst_status"] == 1
    if flagged and actual:  tp += 1
    elif flagged and not actual: fp += 1
    elif not flagged and actual: fn += 1
    else:                        tn += 1

precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

print("-- Results -----------------------------------------------------------------")
print(f"  True  Positives (burst flagged):     {tp}")
print(f"  False Positives (normal flagged):    {fp}")
print(f"  False Negatives (burst missed):      {fn}")
print(f"  True  Negatives (normal correct):    {tn}")
print()
print(f"  Precision : {precision:.2%}  (of flagged, what fraction were real bursts?)")
print(f"  Recall    : {recall:.2%}  (of real bursts, what fraction were flagged?)")
print(f"  F1        : {f1:.2%}")
print()
print("-- Caveat ------------------------------------------------------------------")
print(f"  Only {burst_count} burst rows in the test set -- numbers are noisy.")
print("  Recall is the more important metric here: missing a burst is worse")
print("  than a false alarm. Lower PRESSURE_DROP_THRESHOLD if recall is poor.")
