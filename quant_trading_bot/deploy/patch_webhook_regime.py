p = "/opt/eth-paper/paper_webhook.py"; s = open(p).read()
helper = '''

def regime_line(summary):
    r = (summary or {}).get("regime") or {}
    if not r or r.get("error"):
        return ""
    col = "#ff5c5c" if r["slope"] < 0 else "#2ecc71"
    return (f'<div class="muted" style="margin-top:8px">Vol regime (prior close {r["as_of"]}): VIX {r["vix"]} / VIX3M {r["vix3m"]} &middot; '
            f'<b style="color:{col}">{r["state"]}</b> (slope {r["slope"]:+.1%}, VIX 1y pct {r["vix_rank_1y"]:.0%}) &middot; {r["note"]}</div>')

'''
assert "def render_futures" in s and "def regime_line" not in s
s = s.replace("\n\ndef render_futures(summary):", helper + "\ndef render_futures(summary):", 1)
old1 = 'body = (f\'<div class="grid">{"".join(cards)}</div>\''
old2 = 'f\'<div class="grid">{"".join(cards)}</div>\'\n            f\'<section class="total"><h2>All {len(cards)} futures candidates'
assert old1 in s and old2 in s
s = s.replace(old1, 'body = (regime_line(summary) + f\'<div class="grid">{"".join(cards)}</div>\'', 1)
s = s.replace(old2, 'regime_line(summary) + f\'<div class="grid">{"".join(cards)}</div>\'\n            f\'<section class="total"><h2>All {len(cards)} futures candidates', 1)
open(p, "w").write(s); print("patched", s.count("regime_line(summary)"))
