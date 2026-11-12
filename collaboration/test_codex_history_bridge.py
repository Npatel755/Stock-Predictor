import json
from pathlib import Path
import tempfile
import unittest
from shared_history import parse_codex, redact, write_codex, write_unified, timeline_events


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def source(self, entries):
        p = self.root / 'rollout.jsonl'
        records = [dict(type='session_meta', payload=dict(id='approved', cwd=str(self.root)))] + entries
        p.write_text(''.join(json.dumps(x) + '\n' for x in records), encoding='utf-8')
        return p

    def message(self, role, text, phase=None, channel=None, identity='m1'):
        return dict(timestamp='2026-11-11T14:00:00Z', type='response_item', payload=dict(
            id=identity, type='message', role=role, phase=phase, channel=channel,
            content=[dict(type='input_text' if role == 'user' else 'output_text', text=text)]))

    def test_only_visible_roles_and_phases(self):
        p = self.source([self.message('system', 'PRIVATE', identity='s'), self.message('developer', 'PRIVATE', identity='d'),
            self.message('assistant', 'PRIVATE', 'analysis', identity='a'), self.message('assistant', 'PRIVATE', 'final', 'analysis', 'ac'),
            dict(type='response_item', payload=dict(type='function_call_output', output='PRIVATE')),
            dict(type='response_item', payload=dict(type='reasoning', summary='PRIVATE')),
            self.message('user', 'Hello', identity='u'), self.message('assistant', 'Reply', 'final_answer', identity='f'),
            self.message('assistant', 'Update', 'commentary', identity='c')])
        r = parse_codex(p, 'approved', self.root)
        self.assertEqual([x['content'] for x in r], ['Hello', 'Reply', 'Update'])
        self.assertNotIn('PRIVATE', json.dumps(r))

    def test_scope_mismatch_fails_closed(self):
        p = self.source([self.message('user', 'Hello')])
        with self.assertRaises(ValueError):
            parse_codex(p, 'different', self.root)
        with self.assertRaises(ValueError):
            parse_codex(p, 'approved', self.root / 'other')

    def test_duplicate_ids_partial_append_and_environment(self):
        m = self.message('user', 'Hello')
        p = self.source([m, m, self.message('user', '<environment_context>runtime</environment_context>', identity='e')])
        with p.open('a') as f:
            f.write('{"partial":')
        self.assertEqual(len(parse_codex(p, 'approved', self.root)), 1)

    def test_redacts_common_pasted_credentials(self):
        for text in ('sk-proj-' + 'A' * 30, 'apk_user_' + 'B' * 30, 'Bearer ' + 'C' * 30, 'api_key="' + 'D' * 30 + '"'):
            self.assertIn('[REDACTED_CREDENTIAL]', redact(text))

    def test_four_sources_survive_repeated_renderer_calls(self):
        for a in ('ANTIGRAVITY', 'CLAUDE'):
            (self.root / (a + '_FULL_CHAT_HISTORY.jsonl')).write_text(json.dumps(dict(timestamp='2026-11-11T14:00:00Z', user_prompt='Question', assistant_response='Answer')) + '\n')
        (self.root / 'DEVIN_FULL_CHAT_HISTORY.jsonl').write_text(json.dumps(dict(timestamp='2026-11-11T13:00:00Z', type='devin_message', message='Answer')) + '\n')
        write_codex(parse_codex(self.source([self.message('user', 'Codex question')]), 'approved', self.root), self.root)
        self.assertEqual(write_unified(self.root), 6)
        self.assertEqual(write_unified(self.root), 6)
        md = (self.root / 'UNIFIED_COLLABORATION_STREAM.md').read_text(encoding='utf-8')
        self.assertIn('Codex question', md)
        self.assertEqual({r['agent'] for r in timeline_events(self.root)}, {'Antigravity', 'Claude', 'Devin', 'Codex'})
        self.assertEqual(timeline_events(self.root)[0]['agent'], 'Devin')


if __name__ == '__main__':
    unittest.main()
