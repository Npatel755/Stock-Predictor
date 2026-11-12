"""Local, explicitly scoped Codex chat mirror. Uses no API or credentials."""
from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
import time
from shared_history import ROOT, atomic_write, now, parse_codex, write_codex, write_unified

CONFIG = ROOT / 'codex_history_config.json'
STATUS = ROOT / 'codex_history_status.json'


def sources(config):
    return [Path(t['rollout_path']) for t in config['threads']] + [ROOT / (a + '_FULL_CHAT_HISTORY.jsonl') for a in ('ANTIGRAVITY', 'CLAUDE', 'DEVIN')]


def sync(config):
    records = []
    for thread in config['threads']:
        records += parse_codex(thread['rollout_path'], thread['thread_id'], config['project_root'])
    write_codex(records)
    count = write_unified()
    value = dict(updated_at=now(), status='ok', approved_thread_count=len(config['threads']),
        codex_visible_messages=len(records), unified_cached_events=count, network_calls=0,
        scope='Approved project thread only; visible user/assistant text; no reasoning/tool payloads',
        source_mirrors={a:dict(exists=(ROOT / (a + '_FULL_CHAT_HISTORY.jsonl')).exists(),
            modified_unix=(ROOT / (a + '_FULL_CHAT_HISTORY.jsonl')).stat().st_mtime if (ROOT / (a + '_FULL_CHAT_HISTORY.jsonl')).exists() else None) for a in ('ANTIGRAVITY', 'CLAUDE', 'DEVIN')})
    atomic_write(STATUS, json.dumps(value, indent=2) + '\n')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=int, default=5)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    previous = None
    while True:
        try:
            config = json.loads(CONFIG.read_text(encoding='utf-8'))
            if not config.get('enabled', False):
                logging.info('Codex sharing disabled; exiting.')
                return
            stamps = [(str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (str(p), None) for p in [CONFIG, *sources(config)]]
            if stamps != previous:
                value = sync(config)
                previous = stamps
                logging.info('Synced %d Codex messages; %d cached timeline events', value['codex_visible_messages'], value['unified_cached_events'])
            if not args.watch:
                print(json.dumps(json.loads(STATUS.read_text(encoding='utf-8'))))
                return
        except Exception as error:
            # Keep previous mirrors intact on malformed/unavailable source.
            atomic_write(STATUS, json.dumps(dict(updated_at=now(), status='error', error_type=type(error).__name__)) + '\n')
            logging.error('Sync failed: %s; existing history preserved', type(error).__name__)
            if not args.watch:
                raise
        time.sleep(max(1, args.interval))


if __name__ == '__main__':
    main()
