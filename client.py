"""Shared Ace Data Cloud transport, compiled unchanged into each installable plugin.

The public Dify adapters informed the async contract. Hermes handlers deliberately
use a bounded poll and a compact allowlisted result, never replay a submission.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

BASE_URL = 'https://api.acedata.cloud'
KEY_ENV = 'ACEDATACLOUD_API_KEY'
DONE = {'complete', 'completed', 'succeeded', 'succeed', 'success', 'finished'}
FAILED = {'failed', 'error', 'cancelled', 'canceled', 'rejected'}
MEDIA_KEYS = {'image_url', 'audio_url', 'video_url', 'file_url', 'raw_image_url', 'url'}
OUTPUT_KEYS = MEDIA_KEYS | {'id', 'task_id', 'state', 'status', 'title', 'duration', 'width', 'height', 'format', 'model', 'lyric', 'text', 'data', 'content', 'success', 'images', 'videos', 'audios', 'items', 'organic', 'news', 'places', 'maps', 'link', 'snippet', 'position', 'date', 'source', 'imageUrl', 'thumbnailUrl', 'imageWidth', 'imageHeight', 'address', 'rating', 'ratingCount', 'latitude', 'longitude', 'face_model_version', 'face_shape_set', 'image_height', 'image_width', 'face_profile', 'left_eye', 'right_eye', 'left_eyebrow', 'right_eyebrow', 'mouth', 'nose', 'left_pupil', 'right_pupil', 'x', 'y'}
OUTPUT_KEYS |= {'task', 'image_id', 'progress', 'raw_image_height', 'raw_image_width', 'resolution', 'ratio'}


class ApiError(Exception):
    def __init__(self, code, message, *, http_status=None, trace_id=None):
        super().__init__(message)
        self.result = {'status': 'error', 'success': False, 'error': {'code': code, 'message': message}}
        if http_status is not None:
            self.result['http_status'] = http_status
        if trace_id:
            self.result['trace_id'] = trace_id


def api_key():
    # Resolve at call time: no cross-profile key or client cache.
    from agent.secret_scope import get_secret
    value = (get_secret(KEY_ENV) or '').strip()
    if not value:
        raise ApiError('missing_credentials', f'Set {KEY_ENV} in the active Hermes profile before using this plugin.')
    return value


def available():
    try:
        return bool(api_key())
    except Exception:
        return False


def request(path, body, *, headers=None, timeout=30):
    from hermes_cli.urllib_security import open_credentialed_url
    req = urllib.request.Request(
        BASE_URL + path, data=json.dumps(body).encode(), method='POST',
        headers={'Authorization': 'Bearer ' + api_key(), 'Content-Type': 'application/json',
                 'Accept': 'application/json', **(headers or {})},
    )
    try:
        # Hermes prevents credential forwarding across origin redirects.
        with open_credentialed_url(req, timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ApiError('response_too_large', 'Response exceeded the limit. Check request history before submitting again.')
            result = json.loads(raw)
            if isinstance(result, dict):
                result.setdefault('trace_id', response.headers.get('x-trace-id', ''))
            return result
    except urllib.error.HTTPError as error:
        raise ApiError('http_error', 'Ace Data Cloud rejected the request. Check service access, balance and request history before resubmitting.',
                       http_status=error.code, trace_id=error.headers.get('x-trace-id')) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ApiError('delivery_unknown', 'Connection failed. The request may have been accepted. Do not resubmit automatically; recover the task ID from request history.') from None
    except (ValueError, UnicodeError):
        raise ApiError('invalid_response', 'Invalid JSON response. Check request history before submitting again.') from None


def https_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.fragment
    except ValueError:
        return False


def public_data(value):
    if isinstance(value, dict):
        return {key: public_data(item) for key, item in value.items() if key in OUTPUT_KEYS}
    if isinstance(value, list):
        return [public_data(item) for item in value]
    return value


def media_urls(value, keys=MEDIA_KEYS):
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and https_url(item):
                result.append(item)
            elif isinstance(item, (dict, list)):
                result.extend(media_urls(item, keys))
    elif isinstance(value, list):
        for item in value:
            result.extend(media_urls(item, keys))
    return list(dict.fromkeys(result))


def normalize(body, task_id='', *, retrieved=False, synchronous=False):
    if not isinstance(body, dict):
        raise ApiError('invalid_response', 'Expected a task or generation object; check request history.')
    nested_id = body.get('task', {}).get('id') if isinstance(body.get('task'), dict) else ''
    resolved_id = str(task_id or body.get('task_id') or nested_id or (body.get('id') if not synchronous else '') or '')
    result = body.get('response') if retrieved and 'response' in body else body
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = None
    trace = str(body.get('trace_id') or (result.get('trace_id') if isinstance(result, dict) else '') or '')
    states, failures = [], []

    def visit(node):
        if isinstance(node, dict):
            if node.get('error') or node.get('success') is False:
                failures.append(True)
            for key, value in node.items():
                if key in {'state', 'status'} and isinstance(value, str):
                    states.append(value.lower())
                elif key in {'data', 'content', 'task'}:
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(result)
    outer_failed = bool(body.get('error') or body.get('success') is False)
    if outer_failed:
        failures.append(True)
    failed = bool(failures or any(state in FAILED for state in states))
    unfinished = retrieved and 'finished_at' in body and body['finished_at'] is None
    safe = public_data(result) if result is not None else {}
    urls = media_urls(safe)
    done = (synchronous and bool(result)) or (bool(states) and all(state in DONE for state in states)) or (
        not states and bool(urls) and (not retrieved or bool(body.get('finished_at'))))
    if outer_failed:
        status = 'failed'
    elif unfinished:
        # Task responses can contain an intermediate failed attempt while the
        # server is still processing. Only finished_at makes that response final.
        status = 'pending'
    elif failed:
        status = 'failed'
    elif done:
        status = 'succeeded'
    elif resolved_id:
        status = 'pending'
    else:
        raise ApiError('delivery_unknown', 'No completed result or task ID. Check request history before submitting again.')
    output = {'status': status, 'success': status == 'succeeded', 'task_id': resolved_id,
              'trace_id': trace, 'media_urls': urls if status == 'succeeded' else [],
              'data': safe if status == 'succeeded' else {}}
    if status == 'failed':
        output['error'] = {'code': 'generation_failed', 'message': 'Generation failed. Inspect the task or trace ID; do not resubmit automatically.'}
    if status == 'pending':
        output['next_action'] = 'Retrieve this task ID again; do not submit another generation.'
    return output


def validate(args, schema):
    # jsonschema is not required: validate the small declared subset exactly.
    if not isinstance(args, dict) or set(args) - set(schema['properties']):
        raise ValueError('Unsupported parameters.')
    for name in schema.get('required', []):
        if name not in args:
            raise ValueError(f'{name} is required.')
    for name, value in args.items():
        field = schema['properties'][name]
        kind = field['type']
        types = {'string': str, 'integer': int, 'boolean': bool, 'array': list}
        if not isinstance(value, types[kind]) or kind == 'integer' and isinstance(value, bool):
            raise ValueError(f'{name} has an invalid type.')
        if 'enum' in field and value not in field['enum']:
            raise ValueError(f'{name} is not supported.')
        if kind == 'string' and (not value.strip() or len(value) > field.get('maxLength', 10000)):
            raise ValueError(f'{name} must be nonempty and within the length limit.')
        if kind == 'string' and field.get('format') == 'uri' and not https_url(value):
            raise ValueError(f'{name} must be an HTTPS URL without embedded credentials.')
        if kind == 'string' and field.get('pattern') and not re.fullmatch(field['pattern'], value):
            raise ValueError(f'{name} has an invalid format.')
        if kind == 'integer' and not field.get('minimum', 0) <= value <= field.get('maximum', 10000):
            raise ValueError(f'{name} is outside the allowed range.')
        if kind == 'array':
            if not field.get('minItems', 0) <= len(value) <= field.get('maxItems', 4) or not all(https_url(item) for item in value):
                raise ValueError(f'{name} must contain the allowed number of HTTPS media URLs.')


class MediaClient:
    def __init__(self, spec):
        self.spec = spec

    def generate(self, args):
        validate(args, self.spec['generate_schema'])
        body = {**self.spec['defaults'], **args}
        if self.spec.get('task_path'):
            body['async'] = True
        headers = {}
        if self.spec['service'] == 'fish':
            headers['model'] = body.pop('model')
        if self.spec['service'] == 'nano-banana':
            body['action'] = 'edit' if body.get('image_urls') else 'generate'
        if self.spec['service'] == 'veo':
            body['action'] = 'image2video' if body.get('image_urls') else 'text2video'
            if body['action'] == 'text2video':
                body.pop('aspect_ratio', None)
        if self.spec['service'] == 'suno':
            if not body.get('custom') and not body.get('prompt'):
                raise ValueError('A music description is required.')
            if body.get('custom') and (not body.get('title') or not body.get('style')):
                raise ValueError('Custom music requires title and style.')
            if body.get('custom') and not body.get('instrumental') and not body.get('lyric'):
                raise ValueError('Custom vocal music requires lyric.')
        if self.spec['service'] in {'seedance', 'minimax'}:
            body['content'] = [{'type': 'text', 'text': body.pop('prompt')}]
            if body.get('first_frame_url'):
                body['content'].append({'type': 'image_url', 'image_url': {'url': body.pop('first_frame_url')}, 'role': 'first_frame'})
        result = normalize(request(self.spec['generate_path'], body, headers=headers), synchronous=not self.spec.get('task_path'))
        if result['status'] == 'succeeded' and self.spec['service'] in {'google-search', 'face'}:
            data = result['data'].get('data', result['data'])
            expected = {'organic', 'news'} if self.spec['service'] == 'google-search' else {'face_shape_set', 'image_width', 'image_height'}
            if not isinstance(data, dict) or not expected.intersection(data):
                raise ApiError('invalid_response', 'The synchronous response is missing its documented result fields. Check the request trace before retrying.')
        return self.check_media(result)

    def check_media(self, result):
        if self.spec.get('task_path') and result['status'] == 'succeeded':
            kind = self.spec.get('kind', 'image')
            keys = {'audio_url', 'url'} if kind == 'audio' else {'video_url', 'url'} if kind == 'video' else {'image_url', 'raw_image_url', 'url'}
            result['media_urls'] = media_urls(result.get('data', {}), keys)
        if self.spec.get('task_path') and result['status'] == 'succeeded' and not result['media_urls']:
            result.update(status='failed', success=False, error={'code': 'missing_media', 'message': 'The task finished without a media URL. Inspect this task ID before any resubmission.'})
        return result

    def retrieve(self, args):
        validate(args, self.spec['task_schema'])
        task_id = args['task_id']
        deadline = time.monotonic() + args.get('wait_seconds', 0)
        while True:
            try:
                timeout = min(30, max(1, deadline - time.monotonic())) if args.get('wait_seconds', 0) else 30
                result = normalize(request(self.spec['task_path'], {'action': 'retrieve', 'id': task_id}, timeout=timeout), task_id, retrieved=True)
            except ApiError as error:
                error.result['task_id'] = task_id
                error.result['next_action'] = 'Retry retrieval of this same task ID; never repeat the generation to recover a query failure.'
                return error.result
            if result['status'] != 'pending' or time.monotonic() >= deadline:
                return self.check_media(result)
            time.sleep(min(5, max(0, deadline - time.monotonic())))
            if time.monotonic() >= deadline:
                return result


def handler(client, operation):
    def invoke(args, **kwargs):
        try:
            return json.dumps(getattr(client, operation)(args), ensure_ascii=False)
        except ApiError as error:
            return json.dumps(error.result)
        except ValueError as error:
            return json.dumps({'status': 'error', 'success': False, 'error': {'code': 'invalid_parameters', 'message': str(error)}})
        except Exception:
            return json.dumps({'status': 'error', 'success': False, 'error': {'code': 'plugin_error', 'message': 'Plugin operation failed. Check request history before submitting again.'}})
    return invoke
