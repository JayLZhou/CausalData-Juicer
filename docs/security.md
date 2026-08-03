# Security model

This page states plainly what the engine does and does not protect, so you
can decide what to run it on. The short version: **treat every collection
run as executing untrusted code on your machine**, because it does.

## What executes where

| Component | What runs | Isolation today |
|---|---|---|
| Verifier (`pytest`, `--verify` command) | your repo's code + model-edited files | **none — host process** |
| Agent tool calls (`write_file`, `read_file`) | file ops inside a workspace copy | path-checked (see below) |
| Candidate fixes / replay branches | model-generated code, executed by the verifier | **none — host process** |
| Bench environments | pinned venvs under `bench_envs/` | separate interpreters, same host |

The class doing workspace materialization is named `UnsafeLocalWorkspace`
on purpose. It isolates **state between replay branches** (each fork gets
its own tree — that's what paired counterfactuals need). It is **not** a
security boundary: no container, no syscall filter, no network isolation,
no resource limits. A malicious repo, or a model-generated patch, can do
anything your user account can. `cdj run` on an untrusted repo therefore
requires the explicit `--unsafe-local-execution` flag.

**Planned safe default**: a rootless container backend (Docker/Podman) with
network disabled, non-root user, workspace-only mount, CPU/memory/pids/disk
limits and timeouts, and no secrets, git credentials, or docker socket
mounted. Until that lands, the flag stays.

## Path safety

All agent-supplied paths (including those inside imported traces, which are
untrusted) resolve through a single choke point,
`runtime/paths.resolve_workspace_path`: absolute paths, `..` components,
intermediate symlinks, and symlinks resolving outside the workspace are all
rejected; a `realpath` containment check backstops the walk. The attack
suite is `tests/test_path_safety.py`.

## What reaches the LLM

Prompt context is built by `runtime/context.py`: an extension **allowlist**
(never "all text files"), a deny-list for secret-bearing names (`.env*`,
keys, PEM, `.npmrc`, `.pypirc`, credentials, cloud configs), symlinks never
followed, and surviving text scanned for token shapes (AWS/GitHub/OpenAI/
Slack/JWT, PEM blocks, `key=value` credentials) plus high-entropy strings,
which are replaced with `[REDACTED]`. `cdj run` prints the exact file list
before the first LLM call; `cdj run --context-manifest` prints it and
exits. Redaction is best-effort pattern matching — do not point the engine
at a repo whose *file contents themselves* must never leave the machine,
and prefer a local endpoint for anything sensitive.

The LLM disk cache can embed prompt material, so it is written `0600` in a
`0700` directory; `CDJ_LLM_CACHE=off` disables it, `CDJ_LLM_CACHE_TTL`
(seconds) expires entries.

## Deletion safety

The engine only ever clears directories it created: run directories carry a
`.cdj-managed` marker, unmarked directories are refused, and "clearing"
is an atomic move into a sibling `.cdj-trash/` rather than deletion
(`runtime/rundir.py`). Workspace disposal is confined to the run's scratch
root.

## Reporting

Found a hole? Please open a GitHub issue (or a private security advisory on
the repository) with a reproducer. Path escapes, secret leakage into
prompts/caches/exports, and deletion outside managed directories are all
in-scope and considered bugs, not caveats.
