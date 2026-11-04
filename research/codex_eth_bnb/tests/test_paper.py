import hashlib
import json

import pandas as pd
import pytest

from research.codex_eth_bnb.paper import (assert_prospective_ready, emit_paper_signal,
                                         freeze_payload, load_frozen_config, main)


def frozen(tmp_path):
    for name in ['strategy.py', 'data_manifest.json', 'split_manifest.json']:
        (tmp_path/name).write_text('{}' if name.endswith('.json') else '# frozen code\n', encoding='utf-8')
    sha = lambda name: hashlib.sha256((tmp_path/name).read_bytes()).hexdigest()
    return freeze_payload(dict(mode='paper_only', strategy=dict(id='flat_1h', family='flat', timeframe='1h', parameters={}),
                               code_hashes={'strategy.py': sha('strategy.py')},
                               data_manifest_sha256=sha('data_manifest.json'), split_manifest_sha256=sha('split_manifest.json'),
                               prospective_reservation=dict(start='2026-11-05T00:00:00+00:00', end='2027-05-04T00:00:00+00:00')))


def bars():
    frame = pd.DataFrame(dict(timestamp=pd.date_range('2026-11-05', periods=3, freq='1h', tz='UTC'),
                              open=100., high=101., low=99., close=100., volume=1000.))
    frame.attrs['timeframe'] = '1h'
    return frame


def test_completed_candle_emits_only_paper_direction(tmp_path):
    output = emit_paper_signal(bars(), frozen(tmp_path), observed_at='2026-11-05T03:00:00+00:00')
    assert output['mode'] == 'paper_only'
    assert output['execution_enabled'] is False
    assert output['desired_paper_direction'] == 0
    assert output['signal_bar_open'] == '2026-11-05T02:00:00+00:00'
    assert output['available_at'] == '2026-11-05T03:00:00+00:00'
    assert 'fill_price' not in output


def test_future_or_incomplete_candle_rejected(tmp_path):
    with pytest.raises(ValueError, match='future or incomplete'):
        emit_paper_signal(bars(), frozen(tmp_path), observed_at='2026-11-05T02:59:59+00:00')


def test_future_context_rejected_even_when_target_is_completed(tmp_path):
    source = bars()
    source.timestamp += pd.Timedelta(hours=1)
    with pytest.raises(ValueError, match='context contains a future'):
        emit_paper_signal(bars(), frozen(tmp_path), context={'BTC': source}, observed_at='2026-11-05T03:00:00+00:00')


def test_payload_change_rejected(tmp_path):
    config = frozen(tmp_path)
    config['strategy']['parameters']['lookback'] = 99
    with pytest.raises(ValueError, match='payload hash changed'):
        emit_paper_signal(bars(), config, observed_at='2026-11-05T03:00:00+00:00')


def test_caller_injected_features_are_recomputed(tmp_path):
    config = frozen(tmp_path)
    config['strategy'] = dict(id='tsmom_1h', family='tsmom', timeframe='1h', parameters=dict(lookback=1, threshold=.1))
    config = freeze_payload(config)
    data = bars()
    data['close'] = [99., 100., 100.5]
    data['atr'], data['regime'], data['htf_trend'], data['session_vwap'] = 1., 'trend', 1., 90.
    data['rv'], data['ema_fast'], data['ema_slow'] = .00001, 101., 99.
    result = emit_paper_signal(data, config, observed_at='2026-11-05T03:00:00+00:00')
    assert result['desired_paper_direction'] == 0  # Real ATR is still warming up.


def test_changed_code_rejected_at_config_reader(tmp_path):
    config = frozen(tmp_path)
    path = tmp_path/'candidate.json'
    path.write_text(json.dumps(config), encoding='utf-8')
    assert load_frozen_config(path, tmp_path)['freeze_sha256'] == config['freeze_sha256']
    (tmp_path/'strategy.py').write_text('# revised code\n', encoding='utf-8')
    with pytest.raises(ValueError, match='code hash changed'):
        load_frozen_config(path, tmp_path)


def test_prospective_gate_checks_time_and_manifest_identity(tmp_path):
    config = frozen(tmp_path)
    with pytest.raises(ValueError, match='remains sealed'):
        assert_prospective_ready(config, '2027-05-03T23:59:59+00:00', root=tmp_path)
    assert assert_prospective_ready(config, '2027-05-04T00:00:00+00:00', root=tmp_path)
    (tmp_path/'split_manifest.json').write_text('{"revised":true}', encoding='utf-8')
    with pytest.raises(ValueError, match='manifest hash changed'):
        assert_prospective_ready(config, '2027-05-04T00:00:00+00:00', root=tmp_path)


def test_naive_time_and_non_paper_mode_rejected(tmp_path):
    with pytest.raises(ValueError, match='UTC-aware'):
        emit_paper_signal(bars(), frozen(tmp_path), observed_at='2026-11-05 03:00')
    config = frozen(tmp_path)
    config['mode'] = 'live'
    with pytest.raises(ValueError, match='paper_only'):
        freeze_payload(config)


def test_cli_writes_only_local_append_file(tmp_path):
    config = frozen(tmp_path)
    cfgpath = tmp_path/'candidate.json'
    cfgpath.write_text(json.dumps(config), encoding='utf-8')
    path = tmp_path/'bars.csv'
    bars().to_csv(path, index=False)
    output = main(['--config', str(cfgpath), '--bars', str(path), '--asof', '2026-11-05T03:00:00+00:00',
                   '--root', str(tmp_path), '--output', 'paper_signals.jsonl'])
    emitted = json.loads((tmp_path/'paper_signals.jsonl').read_text(encoding='utf-8'))
    assert emitted == output
    assert emitted['execution_enabled'] is False
