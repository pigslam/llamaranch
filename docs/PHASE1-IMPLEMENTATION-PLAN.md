# Phase 1 Implementation Plan

## Mission

Build LlamaRanch as a local llama.cpp service manager.

Phase 1 stays intentionally narrow:

* one host
* one user
* local llama.cpp servers only
* systemd user services
* YAML configuration
* no multi-host orchestration
* no routing gateway
* no OpenWebUI/OpenCode abstraction layer yet

The target is to make manually tested llama-server commands reproducible, persistent, inspectable, and restartable.

## Initial Platform

Initial host:

* TheRidge
* openSUSE
* Radeon AI PRO R9700
* llama.cpp Vulkan backend
* stable llama-server path: `~/.local/bin/llama-server`

Systemd mode:

* user services
* not root services

## Core CLI

Required commands:

```bash
llamaranch start <config>
llamaranch stop <config>
llamaranch restart <config>
llamaranch status
llamaranch status <config>
llamaranch logs <config>
llamaranch render <config>
llamaranch validate
llamaranch roundup
```

Optional early commands:

```bash
llamaranch enable <config>
llamaranch disable <config>
llamaranch list
```

Profile-management commands:

```bash
llamaranch new <name>
llamaranch edit <name>
llamaranch clone <source> <destination>
llamaranch delete <name>
llamaranch list
```

## Configuration Directory

Use a simple Git-friendly profile directory:

```text
~/.config/llamaranch/
  configs/
    coder.yaml
    fast-chat.yaml
    long-context.yaml
```

No database in Phase 1.

Each profile is a single YAML file. The file can be addressed by full path or
by basename from `~/.config/llamaranch/configs`, so `coder.yaml` can be started
with `llamaranch start coder`.

The profile is the source of truth. LlamaRanch does not maintain a database or
hidden profile registry.

## Conceptual Objects

### Model

A model defines the GGUF file and model-specific defaults.

```yaml
models:
  qwen36-27b-mtp-q4xl:
    path: /models/qwen/Qwen3.6-27B-MTP-UD-Q4_K_XL.gguf
    context: 32768
    defaults:
      temperature: 0.0
      spec_type: draft-mtp
      spec_draft_n_max: 2
```

### Hardware Target

A hardware target defines the backend and GPU-specific settings.

```yaml
hardware:
  theridge-r9700:
    backend: vulkan
    gpu_layers: -1
    main_gpu: 0
```

### Server

A server combines model, hardware, port, and launch settings. For a single-server
profile, the singular `server` section is named after the YAML file.

```yaml
server:
  model: qwen36-27b-mtp-q4xl
  hardware: theridge-r9700
  host: 0.0.0.0
  port: 8081
  enabled: true
  extra_args:
    - --cache-reuse
```

## Render Behavior

`llamaranch render fast-chat` prints the fully resolved command for
`~/.config/llamaranch/configs/fast-chat.yaml` without starting it.

It shows:

* server name
* model path
* hardware target
* port
* final llama-server command
* generated systemd unit path

This command is critical because it lets manual testing and managed deployment stay aligned.

## Systemd Behavior

Each server maps to one user service:

```text
llamaranch-fast-chat.service
```

Generated unit location:

```text
~/.config/systemd/user/llamaranch-fast-chat.service
```

Expected lifecycle:

```bash
systemctl --user start llamaranch-fast-chat.service
systemctl --user stop llamaranch-fast-chat.service
systemctl --user restart llamaranch-fast-chat.service
journalctl --user -u llamaranch-fast-chat.service -f
```

LlamaRanch wraps these commands.

## Validation

`llamaranch validate` checks:

* config files parse
* referenced models exist
* model paths exist
* hardware targets exist
* server ports are unique
* llama-server executable exists
* generated commands are valid enough to inspect
* systemd unit names are deterministic

Validation does not start services.

## Roundup

`llamaranch roundup` is the operational overview.

Minimum output:

* configured servers
* running/stopped/failed state
* port
* model
* hardware target

Later output modes:

```bash
llamaranch roundup --available
llamaranch roundup --full
```

## Profile Workflow

The primary workflow after the proof of concept is maintaining known-good
profiles:

```text
known-good profile
    ↓
clone
    ↓
modify one setting
    ↓
test
    ↓
keep or delete
```

`llamaranch new <name>` creates a profile from the built-in template.
`llamaranch edit <name>` opens the YAML using `$VISUAL`, `$EDITOR`, then `nano`.
`llamaranch clone <source> <destination>` copies a profile without rewriting the
YAML. `llamaranch delete <name>` confirms before deletion and refuses to delete
a running profile unless forced.

## Implementation Order

1. Build config loading, schema objects, command rendering, and validation.
2. Add systemd unit rendering.
3. Add lifecycle wrappers for start, stop, restart, enable, and disable.
4. Add observability commands for status, logs, and roundup.
5. Expand validation and tests around real-world llama.cpp launch patterns.
