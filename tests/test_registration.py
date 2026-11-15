"""Exercise all valid handlers and native image routing without paid API calls."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location('acedatacloud_media_test', ROOT / '__init__.py',
                                                   submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = plugin
# The native ABC requires Hermes. Plain unit CI covers transport; runtime CI covers it here.
try:
    module_spec.loader.exec_module(plugin)
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith('agent'):
        plugin = None
    else:
        raise


class Context:
    def __init__(self):
        self.tools = {}
        self.providers = []

    def register_tool(self, **args):
        if args['name'] in self.tools:
            raise AssertionError('Duplicate registration')
        self.tools[args['name']] = args

    def register_image_gen_provider(self, provider):
        self.providers.append(provider)


@unittest.skipUnless(plugin, 'Run with Hermes runtime to test the public provider ABC')
class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Context()
        plugin.register(self.ctx)

    def test_every_registered_handler_routes_its_own_service(self):
        self.assertEqual(len(self.ctx.tools), sum(len(s['tools']) for s in plugin.SERVICES))
        self.assertEqual(len({t['toolset'] for t in self.ctx.tools.values()}), len(plugin.SERVICES))
        for spec in plugin.SERVICES:
            with self.subTest(service=spec['service']):
                args = {k: 'https://example.com/a.jpg' if k.endswith('_url') else 'test'
                        for k in spec['generate_schema']['required']}
                if spec['service'] == 'suno':
                    args = {'prompt': 'A quiet piano melody'}
                response = {'task_id': 'task-123'} if spec['task_path'] else (
                    {'organic': [{'title': 'Docs', 'link': 'https://example.com', 'snippet': 'Guide'}]}
                    if spec['service'] == 'google-search' else
                    {'image_width': 100, 'image_height': 100, 'face_shape_set': []})
                with patch.object(plugin.client, 'request', return_value=response) as request:
                    result = json.loads(self.ctx.tools[spec['generate_name']]['handler'](args))
                self.assertEqual(request.call_count, 1)
                self.assertEqual(request.call_args.args[0], spec['generate_path'])
                self.assertEqual(result['status'], 'pending' if spec['task_path'] else 'succeeded')
                self.assertIn('without a Hermes approval prompt',
                              self.ctx.tools[spec['generate_name']]['schema']['description'])
                description = self.ctx.tools[spec['generate_name']]['schema']['description']
                if spec['task_path']:
                    self.assertIn('Never automatically resubmit generation', description)
                else:
                    self.assertIn('no task-query tool', description)
                    self.assertIn('Never automatically retry a paid request', description)
                if spec['task_path']:
                    key = 'audio_url' if spec['kind'] == 'audio' else 'video_url' if spec['kind'] == 'video' else 'image_url'
                    response = {'finished_at': 123, 'response': {'success': True, 'data': [{key: 'https://example.com/media'}]}}
                    with patch.object(plugin.client, 'request', return_value=response) as request:
                        result = json.loads(self.ctx.tools[spec['tool_prefix'] + '_task']['handler']({'task_id': 'task-123'}))
                    self.assertEqual(request.call_args.args[:2],
                                     (spec['task_path'], {'action': 'retrieve', 'id': 'task-123'}))
                    self.assertTrue(result['success'])

    def test_nano_native_provider_uses_same_task_client(self):
        if not any(s['service'] == 'nano-banana' for s in plugin.SERVICES):
            self.skipTest('No native image provider in this service profile')
        self.assertEqual(len(self.ctx.providers), 1)
        provider = self.ctx.providers[0]
        responses = [{'task_id': 'image-task'}, {'finished_at': 123, 'response': {
            'success': True, 'data': [{'image_url': 'https://example.com/result.png'}]}}]
        with patch.object(plugin.client, 'request', side_effect=responses) as request:
            result = provider.generate('A cube', aspect_ratio='square',
                                       image_url='https://example.com/reference.png')
        self.assertTrue(result['success'])
        self.assertEqual(result['image'], 'https://example.com/result.png')
        self.assertEqual(result['task_id'], 'image-task')
        body = request.call_args_list[0].args[1]
        self.assertEqual(body['action'], 'edit')
        self.assertEqual(body['model'], 'nano-banana-2-lite')
        self.assertEqual(body['count'], 1)
        self.assertEqual(request.call_args_list[1].args[0], '/nano-banana/tasks')

    def test_manifest_exactly_declares_registered_tools_and_shared_key(self):
        manifest = json.loads((ROOT / 'plugin.yaml').read_text())
        self.assertEqual(set(manifest['provides_tools']), set(self.ctx.tools))
        self.assertEqual(manifest['requires_env'], ['ACEDATACLOUD_API_KEY'])
        for name, entry in self.ctx.tools.items():
            self.assertTrue(name.startswith('acedatacloud_'), name)
            self.assertTrue(entry['toolset'].startswith('acedatacloud-'), entry['toolset'])
            self.assertEqual(entry['requires_env'], ['ACEDATACLOUD_API_KEY'])
            self.assertNotIn('override', entry)

    def test_invalid_reference_inputs_never_submit(self):
        spec = next((s for s in plugin.SERVICES if s['service'] == 'nano-banana'), None)
        if spec is None:
            self.skipTest('No Nano Banana in this service profile')
        oversized = 'https://example.com/' + 'a' * 2048
        for url in [oversized, 'https://example.com:bad/image', 'https://example.com/a\nb']:
            with self.subTest(url=url[:50]), patch.object(plugin.client, 'request') as request:
                result = json.loads(self.ctx.tools[spec['generate_name']]['handler'](
                    {'prompt': 'Edit image', 'image_urls': [url]}))
                self.assertEqual(result['error']['code'], 'invalid_parameters')
                request.assert_not_called()
        provider = self.ctx.providers[0]
        for refs in ['https://example.com/image', 123, {'url': 'https://example.com/image'}]:
            with patch.object(plugin.client, 'request') as request:
                result = provider.generate('A cube', reference_image_urls=refs)
                self.assertFalse(result['success'])
                self.assertEqual(result['error_type'], 'invalid_parameters')
                request.assert_not_called()
