"""Nano Banana adapter for the public Hermes image generation provider API."""
from agent.image_gen_provider import ImageGenProvider, success_response, error_response
from .client import ApiError, available


class NanoBananaProvider(ImageGenProvider):
    def __init__(self, client):
        self.client = client

    @property
    def name(self):
        return 'acedatacloud-nano-banana'

    @property
    def display_name(self):
        return 'Ace Data Cloud Nano Banana'

    def is_available(self):
        return available()

    def capabilities(self):
        return {'modalities': ['text', 'image'], 'max_reference_images': 4}

    def list_models(self):
        return [{'id': 'nano-banana-2-lite', 'display': 'Nano Banana 2 Lite'}]

    def get_setup_schema(self):
        return {'name': self.display_name, 'badge': 'paid', 'tag': 'Image generation and editing through Ace Data Cloud',
                'env_vars': [{'key': 'ACEDATACLOUD_API_KEY', 'prompt': 'Ace Data Cloud API key', 'url': 'https://platform.acedata.cloud'}]}

    def generate(self, prompt, aspect_ratio='landscape', *, image_url=None, reference_image_urls=None, **kwargs):
        args = {'prompt': prompt, 'model': 'nano-banana-2-lite', 'count': 1,
                'aspect_ratio': {'square': '1:1', 'portrait': '9:16', 'landscape': '16:9'}.get(aspect_ratio, '16:9')}
        try:
            if reference_image_urls is not None and not isinstance(reference_image_urls, (list, tuple)):
                raise ValueError('Reference images must be a list of HTTPS URLs.')
            refs = ([image_url] if image_url else []) + list(reference_image_urls or [])
            if refs:
                args['image_urls'] = refs
            result = self.client.generate(args)
            if result['status'] == 'pending':
                result = self.client.retrieve({'task_id': result['task_id'], 'wait_seconds': 60})
            if result['status'] == 'succeeded' and result['media_urls']:
                return success_response(image=result['media_urls'][0], model=args['model'], prompt=prompt,
                                        aspect_ratio=aspect_ratio, provider=self.name, modality='image' if refs else 'text',
                                        extra={'task_id': result['task_id'], 'trace_id': result['trace_id']})
            error = error_response(error='Image not completed. Recover with acedatacloud_nano_banana_task using the same task_id; do not generate again.',
                                   error_type=result['status'], provider=self.name, model=args['model'])
            error.update(task_id=result.get('task_id', ''), trace_id=result.get('trace_id', ''))
            return error
        except ApiError as exc:
            return error_response(error=exc.result['error']['message'], error_type=exc.result['error']['code'], provider=self.name)
        except (ValueError, TypeError):
            return error_response(error='Invalid inputs. Use a nonempty prompt and at most four HTTPS references.', error_type='invalid_parameters', provider=self.name)
