"""Behavioral tests: deterministic; no network requests or paid generation."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import client

SPEC = json.loads((ROOT / 'spec.json').read_text())


class ContractTests(unittest.TestCase):
    def test_pending_is_not_success(self):
        result = client.normalize({'task_id': 'task-123'})
        self.assertEqual(result['status'], 'pending')
        self.assertFalse(result['success'])
        self.assertEqual(result['media_urls'], [])

    def test_running_preview_is_not_final(self):
        result = client.normalize({'response': {'success': True, 'data': [{'state': 'running', 'audio_url': 'https://example.com/preview.mp3'}]}, 'finished_at': None}, 'task-123', retrieved=True)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['media_urls'], [])

    def test_mixed_running_batch_is_not_final(self):
        r = client.normalize({'task_id': 't', 'data': [{'state':'complete','audio_url':'https://example.com/a.mp3'}, {'state':'running','audio_url':'https://example.com/b.mp3'}]})
        self.assertEqual(r['status'], 'pending')

    def test_terminal_task_unwraps_json(self):
        r = client.normalize({'response': json.dumps({'success':True, 'data':[{'state':'complete','audio_url':'https://example.com/a.mp3'}]}), 'finished_at':'2026-10-09T00:00:00Z'}, 't', retrieved=True)
        self.assertEqual(r['status'], 'succeeded')
        self.assertEqual(r['media_urls'], ['https://example.com/a.mp3'])
        self.assertEqual(r['task_id'], 't')

    def test_explicit_failure_wins(self):
        r = client.normalize({'success':False,'error':{'message':'private upstream secret'},'task_id':'t','finished_at':None}, 't', retrieved=True)
        self.assertEqual(r['status'], 'failed')
        self.assertNotIn('private', json.dumps(r))

    def test_failed_preview_never_exposes_media(self):
        r = client.normalize({'task_id':'t','data':{'state':'failed','audio_url':'https://example.com/a'}})
        self.assertEqual(r['media_urls'], [])

    def test_empty_response_cannot_complete(self):
        with self.assertRaises(client.ApiError):client.normalize({})
        self.assertEqual(client.normalize({'response':None}, 't', retrieved=True)['status'], 'pending')

    def test_strips_sensitive_unknown_output_fields(self):
        r = client.normalize({'success':True,'data':{'url':'https://example.com/a.png','upstream_model':'private','credential_id':'private','nested_secret':'private'}})
        self.assertNotIn('private', json.dumps(r))

    def test_https_urls(self):
        for u in ['file:///tmp/key','http://example.com/a','https://u:p@example.com/a','https://[bad/a']:
            self.assertFalse(client.https_url(u))
        self.assertTrue(client.https_url('https://example.com/a?q=1'))

    def test_sync_search_keeps_results(self):
        r=client.normalize({'organic':[{'title':'Hermes','link':'https://example.com','snippet':'Plugin docs','position':1}]}, synchronous=True)
        self.assertEqual(r['data']['organic'][0]['snippet'],'Plugin docs')
        self.assertTrue(r['success'])

    def test_schema_rejects_unknown_fields_before_network(self):
        with patch('client.request') as request:
            with self.assertRaises(ValueError):client.MediaClient(SPEC).generate({'unexpected':'value'})
            request.assert_not_called()

    def test_task_wait_bounds_and_id(self):
        for args in [{'task_id':'t','wait_seconds':61}, {'task_id':'t','wait_seconds':True}, {'task_id':'../x'}, {'task_id':''}]:
            with self.assertRaises(ValueError):client.validate(args,SPEC['task_schema'])

    def test_query_error_retains_id(self):
        spec={**SPEC,'task_path':'/test/tasks'}
        with patch('client.request',side_effect=client.ApiError('delivery_unknown','Connection failed.')) as request:
            r=client.MediaClient(spec).retrieve({'task_id':'task-123'})
        self.assertEqual(request.call_count,1)
        self.assertEqual(r['task_id'],'task-123')
        self.assertIn('same task ID',r['next_action'])

    def test_generation_never_retries(self):
        spec={**SPEC,'generate_schema':{'properties':{'prompt':{'type':'string'}},'required':['prompt']},'service':'fixture'}
        with patch('client.request',side_effect=client.ApiError('delivery_unknown','Check request history.')) as request:
            r=json.loads(client.handler(client.MediaClient(spec),'generate')({'prompt':'test'}))
        self.assertEqual(request.call_count,1)
        self.assertEqual(r['error']['code'],'delivery_unknown')

    def test_terminal_without_media_is_not_claimed_success(self):
        r=client.MediaClient({**SPEC,'task_path':'/x/tasks'}).check_media({'status':'succeeded','success':True,'media_urls':[]})
        self.assertFalse(r['success'])

    def test_nested_video_task_contract(self):
        r=client.normalize({'task':{'id':'t','status':'succeeded','content':{'url':'https://example.com/v.mp4'}}})
        self.assertEqual(r['status'],'succeeded')
        self.assertEqual(r['task_id'],'t')
        self.assertEqual(r['media_urls'],['https://example.com/v.mp4'])

    def test_single_url_validation(self):
        schema={'properties':{'image_url':{'type':'string','format':'uri'}}}
        for v in ['http://example.com/x','/tmp/x','https://u:p@example.com']:
            with self.assertRaises(ValueError):client.validate({'image_url':v},schema)

    def test_sync_contract_does_not_claim_empty_envelope(self):
        if SPEC['service'] not in {'google-search','face'}:self.skipTest('asynchronous service')
        args={k:'https://example.com/portrait.jpg' if k=='image_url' else 'test' for k in SPEC['generate_schema']['required']}
        with patch('client.request',return_value={'success':True}):
            with self.assertRaises(client.ApiError):client.MediaClient(SPEC).generate(args)

    def test_declared_defaults_and_request(self):
        args={}
        for k in SPEC['generate_schema']['required']:
            args[k]='https://example.com/image.jpg' if k.endswith('_url') else 'test'
        if SPEC['service']=='suno':args={'prompt':'A short instrumental melody'}
        with patch('client.request',return_value={'task_id':'t'} if SPEC.get('task_path') else {'success':True,'data':{'organic':[],'face_shape_set':[],'image_width':10,'image_height':10}}) as req:
            client.MediaClient(SPEC).generate(args)
        path,body=req.call_args.args
        self.assertEqual(path,SPEC['generate_path'])
        if SPEC.get('task_path'):self.assertIs(body['async'],True)
        if SPEC['service']=='fish':
            self.assertNotIn('model',body)
            self.assertEqual(req.call_args.kwargs['headers']['model'],'s2-pro')
        if SPEC['service'] in {'seedance','minimax'}:
            self.assertEqual(body['content'],[{'type':'text','text':'test'}])
            self.assertNotIn('prompt',body)
        if SPEC['service']=='veo':self.assertNotIn('aspect_ratio',body)


if __name__ == '__main__':unittest.main()
