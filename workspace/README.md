This is the agent's file sandbox.

The `filesystem` MCP tool (through mcpo) can read and write only this
directory. It is shared between:

  WSL2/host : ./workspace
  mcpo      : /workspace

Use it for the smoke test: ask the model to write a file here, then check it
shows up on the host.