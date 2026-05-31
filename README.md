# LlamaRanch

LlamaRanch is an operational management layer for llama.cpp deployments.

Its goal is to provide an Ollama-like model management experience while preserving direct access to native llama.cpp configuration and performance controls.

LlamaRanch manages:

* Hosts
* Slots
* Models
* Presets
* Deployments
* Runtime State

LlamaRanch does not perform inference.

Inference remains the responsibility of llama.cpp.

## Concepts

### Host

A physical machine capable of running llama.cpp.

Examples:

* TheRidge
* Ramon
* KVMBox

### Slot

A named runtime location.

Examples:

* fast-chat
* coder
* long-context
* experimental

### Model

A GGUF model artifact.

### Preset

A saved collection of llama.cpp launch parameters.

### Deployment

A Host + Slot + Model + Preset combination.

### Instance

A running deployment.

## Project Goals

* Simple operational workflow
* Human-readable configuration
* Git-friendly configuration
* Linux-first operation
* Direct compatibility with OpenWebUI

## Non-Goals

* Training models
* Downloading models
* GGUF conversion
* Quantization
* Agent frameworks
* Cloud orchestration
* Replacing llama.cpp
* Replacing OpenWebUI
# LlamaRanch
