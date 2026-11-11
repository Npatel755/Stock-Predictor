from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/v55_check_aegis_train.py").read_text(encoding="utf-8").split('out = {"part_a": part_a()}')[0]
V = {"__name__": "v55", "__file__": str(ROOT / "scripts/v55_check_aegis_train.py")}
exec(src, V)
ep = V["P10"]["ep"]
for k, v in ep.CANDIDATES.items():
    print(f"=== Portfolio {k} ===")
    for s in v.get("sleeves", []):
        print(f"  {s.get('name')}: sym={s.get('symbol')} c={s.get('contracts')} type={s.get('type')}")
