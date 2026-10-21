# Model choices

## Default model

qwen3:8b is the default chat model for the agent and the nightly job.

## Thinking models

Reasoning models such as qwen3.5:4b spend many tokens thinking before answering.
Raise the num_predict limit for them or the reply comes back empty.

## Context length

The compose default is a 16384 token context window, which caps the KV cache size.
