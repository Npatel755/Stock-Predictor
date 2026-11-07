"""Supply an omitted stdlib import to the immutable prepared test runner.

The original freeze/engine/runner bytes and all reservations remain unchanged.
The first launch stopped at archive() before load_test or any new execution.
This launcher supplies only `sys`; it cannot change cohort/strategy settings.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from quant_futures.config import file_hash

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'runs/positive_training_cohort_test_v1'


def load_runner():
    path=ROOT/'scripts/evaluate_positive_training_cohort.py'
    spec=importlib.util.spec_from_file_location('frozen_cohort_entrypoint',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.sys=sys
    return module


if __name__=='__main__':
    module=load_runner()
    receipt=FOLDER/'launcher_import_correction.json'
    correction=dict(launcher_sha256=file_hash(__file__),original_runner_sha256=file_hash(module.__file__),
        correction='Supply omitted standard-library sys import only; original runner bytes unchanged',
        strategy_logic_changed=False,parameters_changed=False,reservations_reset=False,
        first_launch_failed_before_test_price_load=True,new_candidates_executed_before_correction=0)
    if receipt.exists():
        if json.loads(receipt.read_text(encoding='utf-8'))!=correction: raise ValueError('Launcher changed')
    else:
        receipt.write_text(json.dumps(correction,indent=2),encoding='utf-8')
        shutil.copyfile(__file__,FOLDER/'test_launcher.py')
    with module.threadpool_limits(limits=1): module.evaluate()
