"""Register only this plugin's public tools (and Nano Banana's image provider)."""
import json
from pathlib import Path
from .client import MediaClient, available, handler

SPEC = json.loads(Path(__file__).with_name('spec.json').read_text())


def register(ctx):
    client = MediaClient(SPEC)
    operations = [(SPEC['generate_name'], 'generate', SPEC['generate_schema'], SPEC['description'] + ' This operation uses paid Credits. Submit once; recover a pending task by ID.')]
    if SPEC.get('task_path'):
        operations.append((SPEC['tool_prefix'] + '_task', 'retrieve', SPEC['task_schema'], 'Retrieve an existing task; wait at most 60 seconds. Never submits a new generation.'))
    for name, operation, params, description in operations:
        ctx.register_tool(name=name, toolset=SPEC['name'].replace('-', '_'),
                          schema={'name': name, 'description': description, 'parameters': params},
                          handler=handler(client, operation), check_fn=available,
                          requires_env=['ACEDATACLOUD_API_KEY'], description=description)
    if SPEC['service'] == 'nano-banana':
        from .image_provider import NanoBananaProvider
        ctx.register_image_gen_provider(NanoBananaProvider(client))
