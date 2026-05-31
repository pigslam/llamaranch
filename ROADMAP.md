# Roadmap

## Phase 1 - Single Host

Target Host:

* TheRidge

Features:

* Fixed slots
* Start deployments
* Stop deployments
* Restart deployments
* Status reporting
* Log viewing
* Systemd user service integration
* Configuration validation

Out of Scope:

* Remote hosts
* Gateway routing
* Web UI

## Phase 2 - Multi-GPU and Ramon Support

Features:

* Multiple host definitions
* GPU selection
* Device-specific presets
* Tensor split experiments
* Hardware-aware deployments

## Phase 3 - Peer Awareness

Features:

* Remote status
* Remote control
* Remote logs
* Host inventory

## Phase 4 - Gateway

Goal:

Expose a single OpenAI-compatible endpoint.

Example:

OpenWebUI
-> LlamaRanch Gateway
-> TheRidge
-> Ramon

Features:

* Routing
* Model aliases
* Unified endpoint

## Future Ideas

* Web dashboard
* Metrics collection
* Deployment templates
* OpenWebUI integration improvements
