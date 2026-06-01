# PHASE1-VISION.md

# Phase 1 Vision

## Objective

Build a robust local llama.cpp service manager.

Phase 1 is intentionally narrow.

The goal is not orchestration.

The goal is not routing.

The goal is not cluster management.

The goal is reliable local service deployment.

## Initial Target Environment

Host:

* TheRidge

Operating System:

* openSUSE

Primary Hardware:

* Radeon AI PRO R9700

Inference Engine:

* llama.cpp

Stable Executable Path:

```text
~/.local/bin/llama-server
```

## User Experience

A user should define servers once and manage them with simple commands.

Example:

```bash
llamaranch start fast-chat
llamaranch stop fast-chat
llamaranch restart fast-chat
llamaranch status
llamaranch logs fast-chat
```

The user should not need to remember long llama.cpp launch commands.

## Required Features

### Configuration

Human-readable YAML.

Git-friendly.

No database.

### Validation

```bash
llamaranch validate
```

Must verify:

* configuration integrity
* model paths
* hardware references
* port conflicts
* executable availability

### Rendering

```bash
llamaranch render fast-chat
```

Displays:

* resolved configuration
* exact llama-server command
* deployment details

Rendering is a first-class feature.

### Lifecycle Management

```bash
llamaranch start
llamaranch stop
llamaranch restart
```

Implemented through systemd user services.

### Observability

```bash
llamaranch status
llamaranch logs
llamaranch roundup
```

Provides operational visibility into deployed services.

## Explicit Non-Goals

The following are not Phase 1 objectives:

* OpenWebUI abstraction
* OpenCode abstraction
* unified model catalogs
* routing gateways
* request balancing
* distributed inference
* multi-host orchestration
* remote deployment
* automatic service discovery
* cluster scheduling

These capabilities may become future phases.

They should not drive Phase 1 design decisions.

## Design Constraints

LlamaRanch must:

* remain transparent
* expose generated commands
* remain easy to debug
* avoid hidden state
* avoid databases
* remain compatible with manual llama.cpp workflows

LlamaRanch should feel like a thin operational layer above llama.cpp rather than a replacement for it.

## Definition of Done

Phase 1 is complete when a configured server can:

1. Validate successfully.
2. Render its final command.
3. Generate a systemd service.
4. Start successfully.
5. Survive reboot.
6. Expose logs.
7. Be restarted and stopped through the CLI.

At that point LlamaRanch becomes a practical replacement for manually managed llama.cpp server processes.
