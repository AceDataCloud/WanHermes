# Ace Data Cloud Wan for Hermes

![Ace Data Cloud](assets/catalog.png)

Wan 2.6 text-to-video generation through your Ace Data Cloud account.

## Install and configure

Requires Hermes **0.21.6 or newer** and an Ace Data Cloud API key with access to this service and sufficient Credits.

This plugin has been prepared for the official Hermes catalog; listing is pending maintainer review. Until listed, install from the exact reviewed commit shown in the source pull request:

```sh
hermes plugins install https://github.com/AceDataCloud/WanHermes --ref <reviewed-40-character-SHA>
hermes config set ACEDATACLOUD_API_KEY '<your-api-key>'
```

Obtain a key and check current service pricing at [Ace Data Cloud](https://platform.acedata.cloud). Enter the key only into your active Hermes profile; never put it into a chat prompt. Enable this plugin's toolset in `hermes tools` and start a new session. Once officially listed, the catalog install command will be `hermes plugins install acedatacloud-wan`.

## Use

Available tools:

- `acedata_wan_generate`
- `acedata_wan_task`

Example arguments for `acedata_wan_generate`:

```json
{
  "prompt": "A teal paper cube on a cream background."
}
```

The supported input schema and defaults are in [spec.json](spec.json). This initial release covers the primary operation described above; other operations in the broader Ace API/Dify integration are not implied. Unsupported arguments are rejected before a network call. No automatic model fallback is used.

Generation submits once with `async: true`. Save the returned `task_id`. Query `acedata_wan_task` with `{"task_id":"...","wait_seconds":60}` until `status` is `succeeded` or `failed`. A pending response is not success; media is exposed only after completion. Query failures retain the same task ID. There is no automatic resubmission, background poller or webhook. A generation timeout can mean the request was accepted: recover its ID from your Ace request history before doing anything that might charge again.

## Privacy, billing and permissions

- Sends only the requested inputs to `/wan/videos` and task queries to `/wan/tasks` at **https://api.acedata.cloud**, authenticated by **ACEDATACLOUD_API_KEY**. Inputs may be processed by the service. Generation/search/analysis uses your paid Ace account; consult current pricing before invoking.
- Reference URLs are sent to the API for processing. The plugin does not read local media or download returned media; results contain HTTPS links. It never forwards your key to returned media URLs or across origin redirects.
- Reads the declared key at call time through Hermes scoped secrets. No credential files, sibling plugins, OAuth stores, telemetry, shell commands, background processes, auto-updaters or core overrides.
- JSON results use an allowlist of public output fields; errors omit raw service payloads. It stores no credentials, prompts or generated output on disk. Hermes itself can store tool messages in session history.

## Validation and development

```sh
python -m unittest discover -s tests -v
hermes plugins validate . --install-deps
```

CI validates this standalone repository on the official Hermes 0.21.6 source with its own locked runtime. Unit tests use synthetic responses and make no paid calls. Integration evidence is recorded separately when run; passing CI alone is not proof of a live generation or official listing.

The bundled transport is shared Ace Data Cloud code copied into this repository so installation needs no sibling checkout or unpublished package. No third-party Python dependencies are added. Asset `assets/logo.png` is the unmodified [official source](https://cdn.acedata.cloud/assets/logo.png), SHA-256 `3e2c6e2d1a61a549dae2374ec4444c77f4c2617c8f3772bdd4cd6e52bf20767e`; `catalog.png` contains that complete logo on a transparent 1200×600 canvas.

AI-assisted implementation by Ace Data Cloud; reviewed and tested as described in the pull request. MIT licensed.
