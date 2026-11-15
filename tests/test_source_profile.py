"""Downstream contract: generated identity, one service and unchanged operations."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import client

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'source-lock.json').read_text())
SPEC = json.loads(next((ROOT / 'services').glob('*.json')).read_text())


class SourceProfileTests(unittest.TestCase):
    def test_locked_transport_and_operation_contract(self):
        self.assertEqual(hashlib.sha256((ROOT / 'client.py').read_bytes()).hexdigest(), LOCK['transport_sha256'])
        names = {'repo', 'tool_prefix', 'toolset', 'tools', 'generate_name'}
        contract = (json.dumps({k: v for k, v in SPEC.items() if k not in names}, ensure_ascii=False, indent=2) + '\n').encode()
        self.assertEqual(hashlib.sha256(contract).hexdigest(), LOCK['canonical_operation_sha256'])
        self.assertEqual(len(list((ROOT / 'services').glob('*.json'))), 1)

    def test_does_not_override_official_names(self):
        self.assertTrue(all(x.startswith('acedatacloud_single_') for x in SPEC['tools']))
        self.assertTrue(SPEC['toolset'].startswith('acedatacloud-single-'))
        self.assertEqual(len(SPEC['tools']), 2 if SPEC.get('task_path') else 1)

    def test_reference_guards_before_submission(self):
        properties = SPEC['generate_schema']['properties']
        for field in ('image_url', 'image_urls', 'first_frame_url'):
            if field not in properties:
                continue
            for value in ('https://example.com:bad/a.png', 'https://example.com/a\nb.png', 'https://example.com/a b.png'):
                args = {k: 'https://example.com/a.png' if k.endswith('_url') else 'test'
                        for k in SPEC['generate_schema'].get('required', [])}
                if 'prompt' in properties:
                    args['prompt'] = 'test'
                valid_url = 'https://example.com/a.png'
                args[field] = [valid_url] if properties[field]['type'] == 'array' else valid_url
                # Ensure rejection is specifically caused by the bad reference,
                # rather than an unrelated missing/unknown parameter (e.g. Face).
                client.validate(args, SPEC['generate_schema'])
                args[field] = [value] if properties[field]['type'] == 'array' else value
                with self.subTest(field=field, value=value), patch('client.request') as request:
                    with self.assertRaises(ValueError):
                        client.MediaClient(SPEC).generate(args)
                    request.assert_not_called()

    def test_readmes_disclose_source_distribution_and_spending(self):
        text = (ROOT / 'README.md').read_text()
        for phrase in ('without a Hermes approval prompt', 'no automatic retry', 'source-only', '/console/applications?', 'utm_source=opensource', 'utm_medium=referral', 'utm_campaign=evergreen', 'utm_content=', '2026-10-18'):
            self.assertIn(phrase, text)
        self.assertTrue((ROOT / 'readme/README_zh_Hans.md').exists())
