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
its own tree — that's what paired counterfactuals need). It is not, by
itself, a security boundary.

**Execution isolation** (`runtime/exec_backend.py`) is probed at run time
— by actually exercising the capability, never by reading a version string
— and verify commands run at the strongest level the host supports:

| Level | Mechanism | What it guarantees |
|---|---|---|
| `container` | rootless Podman/Docker: `--network=none`, read-only rootfs, workspace-only rw mount, `--cap-drop ALL`, `no-new-privileges`, memory/pids limits, non-root | network off, host fs invisible, resource-bounded **where measured** (see below) |
| `netns` | `unshare -U -r -n` + setrlimit shim | **kernel-enforced network isolation** (even localhost unreachable) + address-space/CPU/file-size limits; **no filesystem isolation** |
| `none` | plain host execution | nothing |

`cdj doctor` prints the level with evidence. At `container` level `cdj run`
proceeds without ceremony; below it, the explicit `--unsafe-local-execution`
flag is required because the filesystem is still exposed.

**Resource limits are measured, not assumed.** Docker prints a warning and
silently ignores `--memory` when the cgroup memory controller is not
available to it. The probe therefore runs a page-touching allocation
against a small cap and records `memory_limit_enforced`; `cdj doctor`
reports "container isolation … WITHOUT enforced memory limits" when that
measurement fails. Note the two levels bound different things: containers
cap **resident** memory via cgroups, while the netns level caps **address
space** via `RLIMIT_AS` — an allocation that is never touched escapes the
former but not the latter.

**When container level actually applies.** The container mounts *only* the
workspace, so the verify command must be runnable with the image's own
toolchain. Workloads pinned to a per-task host venv — what `resolve_command`
produces for the dependency-migration bench — name a host interpreter path
that does not exist inside the image; the engine detects this
(`check_container_compatible`), **downgrades to the next level and prints
the reason** rather than emitting a command that would fail. To keep
container isolation for such a workload, supply an image that carries the
right interpreter and pins via `CDJ_CONTAINER_IMAGE=your/image:tag`. The test suite
(`tests/test_isolation_backend.py`) proves the properties against live
sockets and real allocations — container-level tests run wherever a runtime
works and skip (with the probe's evidence) where it cannot.

Known-hostile host: hardened k8s pods whose AppArmor profile
(`cri-containerd.apparmor.d`) denies all `mount` operations block every
container runtime — rootless Podman installs fine but cannot unpack images
or set up rootfs mounts. On such pods the engine runs at `netns` level;
full container isolation requires the cluster admin to relax the profile
(`container.apparmor.security.beta.kubernetes.io/<name>: unconfined`).

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
