"""One plugin, independently selectable service toolsets, one shared transport."""
import json
from pathlib import Path

from .client import MediaClient, available, handler
from .image_provider import NanoBananaProvider

SERVICES = [
    json.loads(path.read_text())
    for path in sorted(Path(__file__).with_name('services').glob('*.json'))
]


def register(ctx):
    for spec in SERVICES:
        client = MediaClient(spec)
        recovery = (
            ' Submit once; recover pending tasks by ID. Never automatically resubmit generation.'
            if spec.get('task_path') else
            ' Synchronous result; no task-query tool. Never automatically retry a paid request.'
        )
        description = (
            spec['description']
            + ' Spends Ace Data Cloud Credits immediately without a Hermes approval prompt.'
            + ' Model, resolution and count options can increase cost.'
            + ' Inputs go to api.acedata.cloud.' + recovery
        )
        operations = [(spec['generate_name'], 'generate', spec['generate_schema'], description)]
        if spec.get('task_path'):
            operations.append((
                spec['tool_prefix'] + '_task', 'retrieve', spec['task_schema'],
                'Retrieve an existing Ace Data Cloud task; wait at most 60 seconds.'
                ' Never submits a new generation.',
            ))
        for name, operation, parameters, description in operations:
            ctx.register_tool(
                name=name, toolset=spec['toolset'],
                schema={'name': name, 'description': description, 'parameters': parameters},
                handler=handler(client, operation), check_fn=available,
                requires_env=['ACEDATACLOUD_API_KEY'], description=description,
            )
        if spec['service'] == 'nano-banana':
            ctx.register_image_gen_provider(NanoBananaProvider(client))
