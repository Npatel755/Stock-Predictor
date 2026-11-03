"""Fresh replay of all candidates, with immutable ledgers and visual artifacts."""
from .exit_research import freeze
from .strategy_lab import run, directory, sha
from .paths import ROOT


def verify(root=ROOT):
    out = directory(root)
    if not (out/'results.json').exists():
        raise ValueError('Complete the predefined lab experiment first')
    before = {str(p.relative_to(out)): sha(p) for p in out.rglob('*')
              if p.is_file() and p.suffix in {'.parquet', '.csv'}}
    result_hash = sha(out/'results.json')
    run(root, verify=True)
    after = {str(p.relative_to(out)): sha(p) for p in out.rglob('*')
             if p.is_file() and p.suffix in {'.parquet', '.csv'}}
    if before != after or sha(out/'results.json') != result_hash:
        raise ValueError('Fresh lab replay differs from recorded metrics or artifacts')
    proof = dict(results_sha256=result_hash, artifacts_sha256=after,
                  all_candidates_replayed=True, reproduced_exactly=True,
                  independent_future_validation=False)
    freeze(out/'verification_artifacts.json', proof)
    return dict(reproduced_exactly=True, artifacts=len(after), results_sha256=result_hash)


if __name__ == '__main__':
    print(verify())
