# Roadmap

## Product goal

Build a local-first autonomous triage platform that turns signals such as
telemetry, configuration drift, and failing checks into evidence-backed,
human-approved changes. The agent may propose and verify a change, but a human
approves every merge.

```
signals/configs -> triage agent -> scoped tools -> audit trail
                                      |
                                      v
                             tests and verification
                                      |
                                      v
                            draft PR -> human approval -> metrics
```

## Guiding principles

- Local Ollama is the default inference route; cloud fallback is explicit.
- Start read-only and grant narrowly scoped write capabilities only after
  evaluation proves they are reliable.
- Every agent action must have structured, durable audit data.
- A passing verification suite and a draft PR are required before a proposed
  change can reach human review.
- Optimize inference infrastructure only after outcome metrics identify a
  bottleneck.

## Current status (as of 2026-09-17)

**Milestone 1 — Production agent harness: COMPLETE**

- Task schema with ID, source, repo, policy, model, lifecycle state, correlation ID
- Tool registry: read, write, shell, git, network, PR creation
- Per-task permissions, path allowlists, command allowlists, output caps, timeouts
- JSONL audit for prompts, decisions, tool calls, retries, verification, approvals
- Bounded retries with exponential backoff; terminal states: succeeded/needs_review/failed/blocked
- Draft-PR gate: patch on dedicated branch → verification → draft PR → human approval

**Milestone 2 — Evaluation and reliability: COMPLETE**

- Eval suite: `eval/cases/`, `eval/fixtures/`, `eval/history.jsonl`
- Detection, diagnosis, patch, verification cases separated
- Records model, policy version, latency, retries, outcome per run
- Failed eval cases exit non-zero
- Metrics: detection precision/recall, fix success rate, verification pass rate, false-positive rate, rollback rate, human approval rate
- Regression thresholds block promotion of changed policy/model
- **Current:** eval 6/6 passing, history tracked

**Milestone 3 — Scheduled triage: OPERATIONAL**

- Cron at 5 PM daily (`0 17 * * *`) via `scripts/install-cron.sh`
- Waits for Ollama (up to 5 min), logs cleanly if Docker/Ollama down
- Writes `reports/YYYY-MM-DD.md` with git status, GPU status, model list, grep findings
- Cron wrapper: `scripts/run-nightly.sh` (waits up to 5 min for Ollama API)
- Reports in `reports/`

## Next slice (immediate)

Implement the production harness around one controlled workflow:

> Given a known failing test or configuration drift, collect evidence, propose
> the smallest safe patch in an isolated worktree, run verification, write an
> audit trail, and open a draft PR for human approval.

This is the smallest end-to-end proof. It gives evaluation, sensor pipeline,
model router, and vLLM work a stable foundation.

---

## Future milestones (deferred until current slice is solid)

- **Milestone 4** — Model router and fallback policy (Ollama default, cloud opt-in)
- **Milestone 5** — vLLM deployment for RTX 5080 (only if measurements justify)
- **Sensor triage pipeline** — telemetry adapters, drift rules, evidence bundles
- **Multimodal vision** — Qwen2-VL via vLLM (only if use case justifies VRAM cost)