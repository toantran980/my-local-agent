# Project access (`projects_ops`)

`projects_ops` ([`mcp/projects_ops.py`](mcp/projects_ops.py)) is a read-only MCP
server that gives the agent structured, path-safe access to your project
directories. This is opt-in: the volumes are commented out in
`docker-compose.yml` until you enable them.

Related: [README.md](README.md) for the full stack,
[QUICKSTART.md](QUICKSTART.md) for first-time setup.

---

## 1. Create the directories

```bash
cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}"
chmod +x setup-projects.sh
./setup-projects.sh
```

The script prompts for a location — Linux filesystem (WSL2-native, faster) or
Windows filesystem (slower, but reachable from Explorer) — and creates three
directories under it:

```
<base>/
├── projects/    your project directories
├── configs/     config files
└── logs/        log files
```

It also drops a sample project, config, and log file so you can verify access
end to end.

## 2. Enable the volumes

Uncomment the three mounts in the `mcpo` service in `docker-compose.yml`. They
mount read-only (`:ro`):

```yaml
volumes:
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/projects:/projects:ro
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/configs:/configs:ro
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/logs:/logs:ro
```

Pick the default that matches your choice in step 1 — the Linux-native default
won't resolve on a Windows-host setup, and vice versa.

## 3. Restart mcpo and register the tools

```bash
docker compose up -d --force-recreate mcpo
```

Then in Open WebUI: **Admin Panel → Settings → Integrations → External Tool
Servers**, add `http://mcpo:8000/projects_ops`, and enable it in your chat
sessions (tools icon, top right).

## 4. Verify

```bash
./test-projects-ops.sh
```

Or by hand:

```bash
# Confirm mcpo sees the tools
curl -s http://localhost:8000/openapi.json | grep projects_ops

# Read a file
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "", "file_path": "README.md", "base_dir": "/projects"}'

# Check the mount landed
docker exec mcpo ls -la /projects
```

---

## Tools

All five are read-only. Paths are always resolved relative to `base_dir`.

| Tool | Signature | Notes |
| --- | --- | --- |
| `list_projects` | `(base_dir="/projects")` | Directory names only, no contents |
| `list_project_files` | `(project, base_dir="/projects", max_files=30)` | One level of files |
| `get_project_structure` | `(project, base_dir="/projects", max_depth=3)` | Tree view |
| `read_project_file` | `(project, file_path, base_dir="/projects", max_bytes=32000)` | File contents, size-capped |
| `search_projects` | `(pattern, base_dir="/projects", file_pattern="*", max_results=50)` | Regex across all projects |

`base_dir` also accepts `/configs` and `/logs` where the tools are meaningful.

### Example

```bash
curl -X POST http://localhost:8000/projects_ops/search_projects \
  -H "Content-Type: application/json" \
  -d '{"pattern": "TODO|FIXME", "base_dir": "/projects"}'
```

In chat, after registering the server:

```
Use projects_ops to search_projects for "TODO" in /projects
Use projects_ops to get_project_structure for project "myapp"
```

---

## Security model

Every constraint below is enforced in code, not by convention:

- **Path traversal blocked** — paths resolve relative to `base_dir`; `..` and
  absolute escapes are rejected
- **Sensitive files blocked** — `.env`, keys, certificates, and similar
- **Size caps** — 32KB per read (`MAX_FILE_BYTES`), 50 search results
  (`MAX_RESULTS`)
- **Directory exclusions** — `.git`, `node_modules`, `__pycache__`, `.venv`, etc.
- **Read-only** — no write capability, and the volumes mount `:ro`
- **Localhost only** — every service binds to `127.0.0.1`

### Access matrix

| Surface | Directories | Access | Limits |
| --- | --- | --- | --- |
| `filesystem` | `/workspace` | read/write | 32KB read, 1MB write |
| `projects_ops` | `/projects`, `/configs`, `/logs` | read-only | 32KB read |
| `local_ops` | `/repo`, `/data`, `/workspace` | read-only | 32KB read |
| `agent_cli.py` | `--repo` | read; write with `--apply` | 32KB read, 1MB write |

---

## Troubleshooting

**mcpo doesn't see the tools**

```bash
docker compose restart mcpo
docker logs mcpo
```

**Projects directory not accessible**

```bash
docker exec mcpo ls -la /projects
ls -la ~/projects   # does the host path exist and match the compose default?
```

A common cause is a `base_dir` default that doesn't match your setup — the
compose default assumes a Windows host under `/mnt/c/Users/$USER`, but
`setup-projects.sh` may have created the directories on the Linux filesystem
instead.

**Auth proxy fails (if enabled)**

```bash
docker logs auth_proxy
docker exec auth_proxy cat /etc/caddy/Caddyfile
docker exec auth_proxy env | grep ADMIN
```

**Rollback**

Comment out the three volume mounts, remove `projects_ops` from
`mcpo/config.json`, then `docker compose restart mcpo`.
