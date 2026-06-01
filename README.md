# README.md

# LlamaRanch

LlamaRanch is a management layer for llama.cpp.

Its purpose is to make local llama.cpp servers easy to configure, launch, monitor, and persist across reboots.

LlamaRanch does not perform inference.

Inference remains the responsibility of llama.cpp.

Client applications such as OpenWebUI, OpenCode, and custom tooling continue to interact directly with llama.cpp-compatible APIs.

LlamaRanch focuses on operational management:

* configuration
* deployment
* lifecycle management
* observability
* service persistence

## Goals

Running llama.cpp manually often requires:

* long launch commands
* manually managed terminal sessions
* remembering model-specific flags
* recovering services after reboot
* inspecting logs manually

LlamaRanch provides a consistent interface:

```bash
llamaranch start coder
llamaranch stop coder
llamaranch restart coder
llamaranch status
llamaranch logs coder
```

while continuing to use standard llama.cpp servers underneath.

## Core Concepts

### Model

Represents a specific GGUF model and its recommended settings.

Examples:

* Qwen3.6-27B-MTP
* Qwen3.6-35B-A3B
* Gemma
* DeepSeek

### Hardware Target

Represents a specific execution environment.

Examples:

* Radeon AI PRO R9700
* RX 9070
* RTX 2070

Hardware targets encapsulate backend-specific settings and deployment requirements.

### Server

Represents a deployable llama.cpp service.

Examples:

* fast-chat
* coder
* long-context
* experimental

A server combines:

* model
* hardware target
* network settings
* launch parameters

### Instance

A running deployment of a server definition.

An instance may be:

* running
* stopped
* failed

## Configuration Philosophy

Configuration is:

* YAML-based
* human-readable
* Git-friendly
* manually editable

LlamaRanch should never require a database for normal operation.

## Transparency

LlamaRanch must never hide the underlying llama.cpp command.

Every deployment should be inspectable through:

```bash
llamaranch render <config>
```

which displays the fully resolved llama-server command before execution.

## Configuration

Single-file profiles live in:

```text
~/.config/llamaranch/configs/
```

For example, `~/.config/llamaranch/configs/coder.yaml` can be launched with:

```bash
llamaranch start coder
```

You can also pass a direct file path:

```bash
llamaranch start /path/to/coder.yaml
```

A profile keeps the same conceptual sections that were previously split across
separate files:

```yaml
config:
  llama_server: ~/.local/bin/llama-server

models:
  qwen:
    path: /models/qwen.gguf
    context: 32768
    defaults:
      temperature: 0.0

hardware:
  theridge-r9700:
    backend: vulkan
    gpu_layers: -1
    main_gpu: 0

server:
  model: qwen
  hardware: theridge-r9700
  host: 0.0.0.0
  port: 8081
  extra_args:
    - --cache-reuse
```

The singular `server` section is named after the profile file, so `coder.yaml`
creates the `llamaranch-coder.service` unit. A `servers` mapping is also
supported for profiles that intentionally define more than one server; pass
`--server <name>` when rendering or managing one of those entries.

## Profile Management

Profiles are intended to be cloned, edited, tested, kept, or deleted:

```bash
llamaranch new experimental
llamaranch clone coder coder-temp
llamaranch edit coder-temp
llamaranch render coder-temp
llamaranch delete coder-temp
```

`llamaranch list` shows the available profile library with profile name, current
systemd state, port, and model.

`llamaranch delete <name>` asks for confirmation before removing the YAML file.
It refuses to delete a running profile unless `--force` is passed.

## Runtime Model

Phase 1 uses systemd user services.

The generated systemd service is the authoritative runtime object.

Benefits:

* reboot recovery
* restart policies
* centralized logging
* native Linux observability

## Status

LlamaRanch is currently focused on Phase 1:

local llama.cpp service management.

Cluster management, routing, gateway functionality, and multi-host orchestration are future phases.
