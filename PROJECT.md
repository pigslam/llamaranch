# PROJECT.md

# LlamaRanch Project

## Purpose

LlamaRanch exists to solve operational problems around running local llama.cpp servers.

The project originated from practical experience running multiple local models on dedicated AI hardware.

Current workflows require repeatedly constructing and launching large llama.cpp commands by hand.

This creates several recurring problems:

* commands are difficult to remember
* model-specific tuning is easily lost
* services are not persistent
* reboot recovery is manual
* logs are fragmented
* configuration knowledge becomes tribal knowledge

LlamaRanch aims to convert those manual workflows into repeatable infrastructure.

## Guiding Principle

LlamaRanch manages services.

Llama.cpp performs inference.

Clients consume APIs.

Each layer should remain independent.

## Project Scope

The project is intentionally divided into phases.

### Phase 1

Local service management.

Target:

* one host
* one user
* one machine
* one or more local GPUs

Responsibilities:

* configuration management
* command generation
* service deployment
* service lifecycle management
* logging
* validation

### Future Phases

Future work may include:

* multiple hosts
* remote management
* routing
* model abstraction
* gateway services
* OpenWebUI integration
* automatic discovery
* orchestration

These capabilities are explicitly out of scope for Phase 1.

## Architectural Philosophy

Build the smallest useful layer first.

Avoid solving distributed systems problems until local service management is stable.

A successful local foundation should naturally support future expansion.

## Core Objects

### Model

Defines:

* GGUF location
* model defaults
* model tuning

### Hardware Target

Defines:

* backend
* GPU configuration
* host-specific execution settings

### Server

Defines:

* model
* hardware target
* port
* launch behavior

### Instance

Represents a running service.

## Runtime Strategy

Systemd user services are the authoritative deployment mechanism.

LlamaRanch generates and manages systemd units.

LlamaRanch does not replace systemd.

It simplifies interaction with it.

## Success Criteria

The project succeeds when a user can reliably manage llama.cpp deployments using:

```bash
llamaranch validate
llamaranch render fast-chat
llamaranch start fast-chat
llamaranch status
llamaranch logs fast-chat
llamaranch restart fast-chat
llamaranch stop fast-chat
```

without manually constructing or maintaining llama.cpp launch commands.
