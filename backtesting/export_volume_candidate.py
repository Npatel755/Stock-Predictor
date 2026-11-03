"""Export a gated volume/weekend research candidate without changing v1.4."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

from .alternative_strategies import SignalRule
from .config import StrategyConfig
from .export_independent import render
from .optimize import write_json
from .paths import ROOT
from .regime_filters import RegimeFilter


def render_volume(rule, config, filters):
    if rule.family != 'channel_breakout':
        raise ValueError('Volume preview currently requires the channel-breakout family')
    # This narrow exporter must never silently omit a backtested filter.
    supported = replace(filters, min_rvol=0., weekends=True)
    if supported != RegimeFilter():
        raise ValueError('Volume exporter supports only relative-volume and UTC-weekend filters')
    text, _, _ = render(rule, config, version='v1.4')
    payload = dict(rule=asdict(rule), execution=asdict(config), filters=asdict(filters))
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    text = text.replace('ETH v1.4 | Channel Breakout research', 'ETH Volume Research | Experimental candidate', 1)
    text = text.replace('Config SHA-256: ', 'Base geometry SHA-256: ', 1)
    text = text.replace('//@version=6\n', f'//@version=6\n// Experimental filtered candidate; saved v1.4 is unchanged.\n// Full rule/filter/config SHA-256: {digest}\n// Selected using inspected 2023-2026 history, including 2026; no independent forward validation.\n', 1)

    def swap(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError(f'Volume Pine anchor changed: {old}')
        text = text.replace(old, new, 1)

    swap('hourlySignals() =>',
         f'minHourlyRVOL = input.float({filters.min_rvol}, "Minimum completed-hour relative volume", minval=0, step=0.1)\n'
         f'allowWeekends = input.bool({str(filters.weekends).lower()}, "Allow UTC weekends")\n\n'
         'hourlySignals() =>')
    swap('    [ready and longSignal, ready and shortSignal, ta.atr(14)]',
         '    priorMeanVolume = ta.sma(volume[1], 20)\n'
         '    hourlyRVOL = priorMeanVolume > 0 ? volume / priorMeanVolume : na\n'
         '    volumeOK = minHourlyRVOL == 0 or hourlyRVOL >= minHourlyRVOL\n'
         '    [ready and longSignal and volumeOK, ready and shortSignal and volumeOK, ta.atr(14)]')
    swap('longSignal = validChart and hourClosed and hourLong',
         'utcDay = dayofweek(time, "UTC")\n'
         'weekdayOK = allowWeekends or (utcDay >= dayofweek.monday and utcDay <= dayofweek.friday)\n'
         'longSignal = validChart and hourClosed and hourLong and weekdayOK')
    swap('shortSignal = validChart and hourClosed and hourShort',
         'shortSignal = validChart and hourClosed and hourShort and weekdayOK')
    return text, payload, digest


def export(directory: Path):
    selected_path = directory/'selection.json'
    selection = json.loads(selected_path.read_text(encoding='utf-8'))
    if not selection['passed_predeclared_validation_gate']:
        raise ValueError('Refusing to publish a filtered preview that failed its historical gate')
    rule = SignalRule(**selection['candidate']['rule'])
    config = StrategyConfig(**selection['execution_config'])
    filters = RegimeFilter(**selection['candidate']['filters'])
    text, payload, digest = render_volume(rule, config, filters)
    output = ROOT/'reference/experimental/ETH_Volume_Research.pine'
    metadata_path = output.with_suffix('.metadata.json')
    config_path = output.with_suffix('.json')
    if output.exists() and output.read_text(encoding='utf-8') != text:
        archive = ROOT/'reference/revisions'/hashlib.sha256(output.read_bytes()).hexdigest()[:16]
        archive.mkdir(parents=True, exist_ok=True)
        for path in [output, metadata_path, config_path]:
            if path.exists():
                (archive/path.name).write_bytes(path.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding='utf-8')
    write_json(config_path, payload)
    write_json(metadata_path, dict(name='ETH Volume Research', experiment=directory.name,
                                   candidate=selection['candidate']['label'], full_configuration_sha256=digest,
                                   pine_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                                   selection_sha256=hashlib.sha256(selected_path.read_bytes()).hexdigest(),
                                   passed_historical_gate=True, independent_forward_validation=False,
                                   ready_for_funded_trading=False, pine_compilation_verified=False,
                                   tradingview_parity_verified=False,
                                   filters_exported=asdict(filters),
                                   execution_differences=['Pine omits additional basis-point fill slippage, financing and Python stop-first policy',
                                                          'Symbol quantity/tick rounding and history initialization remain unreconciled']))
    download = ROOT/'downloads/ETH_Volume_Research.txt'
    download.parent.mkdir(exist_ok=True)
    download.write_bytes(output.read_bytes())
    print(f'Exported separate experimental preview; v1.4 unchanged: {download}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    export(parser.parse_args().directory)
