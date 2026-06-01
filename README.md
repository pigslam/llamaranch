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
llamaranch start fast-chat
llamaranch stop fast-chat
llamaranch restart fast-chat
llamaranch status
llamaranch logs fast-chat
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
llamaranch render <server>
```

which displays the fully resolved llama-server command before execution.

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
