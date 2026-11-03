"""Faithful signed hourly EMA-distance addition to the volume Pine export."""
from dataclasses import asdict, replace
import hashlib
import json

from .export_volume_candidate import render_volume


def render_trend(rule, config, filters):
    text, _, _ = render_volume(rule, config, replace(filters,min_trend_gap_bps=0.))
    payload=dict(rule=asdict(rule),execution=asdict(config),filters=asdict(filters))
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    lines=text.splitlines()
    lines=[f'// Full rule/filter/config SHA-256: {digest}' if line.startswith('// Full rule/filter/config SHA-256:') else line for line in lines]
    text='\n'.join(lines)+'\n'

    def swap(old,new):
        nonlocal text
        if text.count(old)!=1:raise ValueError(f'Trend Pine anchor changed: {old}')
        text=text.replace(old,new,1)

    swap('hourlySignals() =>',f'minHourlyTrendBps = input.float({filters.min_trend_gap_bps}, "Minimum signed hourly close/EMA gap (bp)", minval=0)\n\nhourlySignals() =>')
    swap('    [ready and longSignal and volumeOK, ready and shortSignal and volumeOK, ta.atr(14)]',
         '    signedLongGap = (close / slow - 1) * 10000\n'
         '    longGapOK = minHourlyTrendBps == 0 or signedLongGap >= minHourlyTrendBps\n'
         '    shortGapOK = minHourlyTrendBps == 0 or -signedLongGap >= minHourlyTrendBps\n'
         '    [ready and longSignal and volumeOK and longGapOK, ready and shortSignal and volumeOK and shortGapOK, ta.atr(14)]')
    return text,payload,digest
