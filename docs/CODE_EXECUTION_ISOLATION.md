# Governed code execution isolation

Production autonomous code verification must run in a separately isolated worker. The API process must not execute untrusted proposal code directly.

Required deployment properties:
- separate worker/container or VM
- non-root user
- network namespace disabled (`--network none` or equivalent)
- read-only worker image
- ephemeral writable workspace only
- no host filesystem mounts beyond the temporary workspace
- no application secrets or credentials in the worker environment
- dropped Linux capabilities and restrictive seccomp or equivalent
- CPU, memory, process-count and wall-clock limits
- bounded stdout/stderr
- allowlisted verification commands only
- destroy the worker after each verification

The worker receives only the approved patch, test command and disposable workspace. It must not receive production database credentials, model-provider keys, auth secrets, backup credentials, or arbitrary environment variables.

`HDS_CODE_RUNNER_MODE=isolated` is a deployment contract. The production orchestrator must enforce these properties before invoking the worker.
