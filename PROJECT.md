# Project Architecture

## Purpose

Provide a lightweight operational control layer for llama.cpp deployments.

LlamaRanch exists to answer:

* What models are available?
* What deployments are configured?
* What is currently running?
* How do I start, stop, or modify deployments?

## Design Principles

1. Linux-first
2. Single-user operation
3. Human-readable configuration
4. Git-friendly configuration
5. No database unless proven necessary
6. No Docker requirement
7. No Kubernetes
8. No cloud dependency
9. llama.cpp remains the inference engine
10. OpenWebUI remains the chat interface

## Configuration Objects

### Host

Represents a machine capable of running deployments.

### Slot

Represents a named runtime position on a host.

Slots are stable identifiers.

Examples:

* fast-chat
* coder
* long-context
* experimental

### Model

Represents a GGUF file.

### Preset

Represents a reusable collection of llama.cpp parameters.

Examples:

* R9700 Fast Chat
* Long Context
* Coding

### Deployment

Represents desired state.

A deployment combines:

* Host
* Slot
* Model
* Preset

### Instance

Represents actual runtime state.

An instance may be:

* running
* stopped
* failed

## Configuration Storage

Configuration should remain:

* plain text
* human editable
* version controlled

Preferred format:

YAML

No database should be introduced without a demonstrated need.
