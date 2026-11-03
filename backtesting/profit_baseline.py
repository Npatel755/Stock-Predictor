"""Current user comparison target, separate from historical version metadata."""
import json


def current_baseline(root, metadata):
    path = root/'configs/research_baseline.json'
    if path.exists():
        target = json.loads(path.read_text(encoding='utf-8'))
        return dict(net=target['requested_net_profit_usd'],
                    period=[target['period_start_utc'], target['period_end_exclusive_utc']],
                    reference_net=target['prior_reference_net_profit_usd'], reference=target['prior_reference'])
    if metadata.get('baseline_net_usd') is not None:
        return dict(net=metadata['baseline_net_usd'], period=metadata['baseline_period'], reference_net=None, reference=None)
    return None
