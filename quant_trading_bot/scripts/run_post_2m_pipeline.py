"""Post-search pipeline for 2M Systematic Training Exploration.

1. Evaluates standout diverse training finalists on Validation (2024-2025) without tuning.
2. Generates comprehensive charts and figures.
3. Generates complete audit report.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / '.venv/Scripts/python.exe'


def run_pipeline():
    ranked_csv = ROOT / 'runs/training_search_2m_v1/ranked.csv'
    if not ranked_csv.exists():
        print(f"Error: {ranked_csv} does not exist yet. Training search has not completed.")
        sys.exit(1)

    print("=== Step 1: Evaluating Standout 2M Finalists on Validation (2024-2025) ===")
    subprocess.run([str(PY), str(ROOT / 'scripts/evaluate_2m_finalists_validation.py')], check=True)

    print("\n=== Step 2: Generating Publication-Grade Visual Charts ===")
    subprocess.run([str(PY), str(ROOT / 'scripts/chart_2m_validation.py')], check=True)

    print("\n=== Pipeline Complete! ===")


if __name__ == '__main__':
    run_pipeline()
