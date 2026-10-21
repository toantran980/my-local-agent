# Agent modes

## ask

Read-only questions. The agent may read files and search but can never write.

## plan

Produces a step-by-step plan without changing anything.

## agent

Stages file edits in memory. Nothing touches disk unless the apply flag is passed,
and tests run against a staged copy first.
