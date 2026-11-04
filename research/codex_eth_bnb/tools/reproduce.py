"""Reproduce the unchanged frozen core even after committing result artifacts."""
from __future__ import annotations

import argparse
import json

from ..data_pipeline import HERE, sha
from ..runner import Lab, code_hashes


def verify():
    frozen = json.loads((HERE/'code_freeze.json').read_text())
    if code_hashes() != frozen['code_hashes']:
        raise ValueError('Research implementation differs from the preregistered execution commit')
    for filename, key in [('candidate_manifest.json','candidate_manifest_sha256'),
                          ('data_manifest.json','data_manifest_sha256'),
                          ('funding_manifest.json','funding_manifest_sha256')]:
        if sha(HERE/filename) != frozen[key]:
            raise ValueError(f'Frozen manifest differs: {filename}')
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    frozen = verify()
    if args.verify_only:
        print('Frozen core code and manifests match execution commit '+frozen['parent_commit'])
        return
    lab = Lab()
    # Later commits add reports/postprocessing only. Core code is byte-identical
    # to this execution revision, the revision recorded in every trial registry.
    lab.revision = frozen['parent_commit']
    training, returns = lab.train()
    chosen = lab.selection(training)
    lab.conditional(training, returns, chosen)
    validated = lab.validate(training, chosen)
    lab.robustness(validated)
    lab.portfolio(chosen)
    from ..legacy import run
    run()
    lab.freeze_candidates(validated)
    from ..reporting import report
    report()
    from .audit_outputs import audit
    audit()
    from .finalize import finalize
    finalize()


if __name__ == '__main__':
    main()
