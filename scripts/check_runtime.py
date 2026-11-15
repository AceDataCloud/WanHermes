"""Normal Git install of an exact source head, alone/co-installed, without API calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'source-lock.json').read_text())
SPEC = json.loads(next((ROOT / 'services').glob('*.json')).read_text())
NAME = json.loads((ROOT / 'plugin.yaml').read_text())['name']


def child(mode, combined):
    from hermes_cli.plugins import discover_plugins, get_plugin_manager, get_plugin_toolsets
    from tools.registry import registry
    from toolsets import resolve_toolset
    from agent.image_gen_registry import get_provider
    discover_plugins()
    manager = get_plugin_manager()
    rows = {r[0] for r in get_plugin_toolsets()}
    assert SPEC['toolset'] in rows, rows
    assert set(resolve_toolset(SPEC['toolset'])) == set(SPEC['tools'])
    for name in SPEC['tools']:
        entry = registry.get_entry(name, scope=manager.scope_key)
        assert entry and entry.toolset == SPEC['toolset'], (mode, name)
    result = registry.dispatch(SPEC['generate_name'], {'unknown': True}, scope=manager.scope_key)
    result = json.loads(result) if isinstance(result, str) else result
    assert result['error']['code'] == 'invalid_parameters', result
    source_sets = {r for r in rows if r.startswith('acedatacloud-single-')}
    assert source_sets == {SPEC['toolset']}, source_sets
    if combined:
        canonical_prefix = LOCK['identity_map']['tool_prefix'][0]
        for name in SPEC['tools']:
            official = name.replace(SPEC['tool_prefix'], canonical_prefix, 1)
            entry = registry.get_entry(official, scope=manager.scope_key)
            assert entry and entry.toolset != SPEC['toolset'], official
        assert len({r for r in rows if r.startswith('acedatacloud-') and not r.startswith('acedatacloud-single-')}) == 17
    else:
        assert {r for r in rows if r.startswith('acedatacloud-')} == {SPEC['toolset']}, rows
    if SPEC['service'] == 'nano-banana':
        provider = get_provider('acedatacloud-single-nano-banana')
        assert provider and not provider.is_available()
        assert '/console/applications?' in provider.get_setup_schema()['env_vars'][0]['url']
        assert provider.list_models()[0]['id'] == 'nano-banana-2-lite'
        if combined:
            assert get_provider('acedatacloud-nano-banana')
    manager.unload()
    print(json.dumps({'service': SPEC['service'], 'mode': mode, 'coinstalled': combined,
                      'source_tools': len(SPEC['tools']), 'official_tools_preserved': combined,
                      'passed': True, 'new_paid_calls': 0}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', choices=['in_process', 'host'])
    parser.add_argument('--combined', action='store_true')
    args = parser.parse_args()
    if args.child:
        child(args.child, args.combined)
        return
    source = Path(os.environ['HERMES_SOURCE']).resolve()
    ref = os.environ.get('PLUGIN_SOURCE_REF') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    for mode in ('in_process', 'host'):
        for combined in (False, True):
            with tempfile.TemporaryDirectory(prefix='hermes-single-service-') as tmp:
                env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'USER', 'LANG', 'TMPDIR', 'HERMES_RUNTIME_DIR'}}
                env.update(HERMES_HOME=tmp, HERMES_PYTHON=sys.executable,
                           PYTHONPATH=str(source), COLUMNS='180')
                Path(tmp, 'config.yaml').write_text(json.dumps({'plugins': {'isolation': mode}}))
                def command(argv):
                    run = subprocess.run([sys.executable, '-m', 'hermes_cli.main', *argv], cwd=source, env=env, capture_output=True, text=True, timeout=180)
                    if run.returncode:
                        raise RuntimeError((argv, run.stdout, run.stderr))
                    return run.stdout
                command(['plugins', 'install', LOCK['consumer_repository'], '--ref', ref, '--enable'])
                if combined:
                    command(['plugins', 'install', 'https://github.com/AceDataCloud/AceDataCloudMediaHermes', '--ref', '8eaebfb86152d754061375de881548bfa096dd2d', '--enable'])
                command(['tools', 'enable', SPEC['toolset']])
                assert SPEC['toolset'] in command(['tools', 'list'])
                installed = Path(tmp, 'plugins', NAME)
                assert len(list((installed / 'services').glob('*.json'))) == 1
                child_args = [sys.executable, str(__file__), '--child', mode]
                if combined:
                    child_args.append('--combined')
                run = subprocess.run(child_args, env=env, cwd=source, capture_output=True, text=True, timeout=240)
                print(run.stdout)
                if run.returncode:
                    raise RuntimeError(run.stderr)


if __name__ == '__main__':
    main()
