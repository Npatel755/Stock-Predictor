import json

from backtesting.profit_baseline import current_baseline


def test_current_target_overrides_original_version_target_without_rewriting_it(tmp_path):
    metadata=dict(baseline_net_usd=6000.,baseline_period=['2023-01-01','2026-10-28'])
    path=tmp_path/'configs/research_baseline.json'
    path.parent.mkdir()
    path.write_text(json.dumps(dict(requested_net_profit_usd=9900.,period_start_utc='2023-01-01',period_end_exclusive_utc='2026-10-28',prior_reference_net_profit_usd=9971.427110129662,prior_reference='ETH v1.5')))
    target=current_baseline(tmp_path,metadata)
    assert target['net']==9900 and target['reference_net']>target['net']
    assert metadata['baseline_net_usd']==6000


def test_old_profile_target_is_available_if_no_current_research_config(tmp_path):
    assert current_baseline(tmp_path,{}) is None
    assert current_baseline(tmp_path,dict(baseline_net_usd=6000.,baseline_period=['2023-01-01','2026-10-28']))['net']==6000
