# Homelab Setup — Safe Project Access via MCP

This guide explains the **implemented** project access layer (`projects_ops` MCP server).

## What's Implemented

### Safe Project Access (`projects_ops` MCP Server)
A read-only MCP server providing secure access to your project directories:

- **Path traversal protection** — all paths resolved relative to base dirs
- **Sensitive file filtering** — blocks `.env`, keys, certs, etc.
- **File size limits** — 32KB read cap
- **Directory exclusions** — `.git`, `node_modules`, `__pycache__`, etc.
- **Structured project exploration** — list, read, search, tree view

### Enhanced Docker Configuration
- Read-only volume mounts for project/config/log directories
- Authentication proxy ready (Caddy, opt-in)
- Security-first networking (localhost-only by default)

### Enhanced `local_ops` Tools
- `projects_overview()` — view available projects
- `configs_overview()` — view config files
- `system_status()` — overall system health
- `gpu_status()` — GPU/model VRAM residency

---

## Setup

### 1. Create directories on Windows host
```bash
# In WSL2
cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}"
chmod +x setup-projects.sh
./setup-projects.sh
# Choose option 2 (Windows filesystem)
```
Creates:
- `C:\Users\<your-username>\projects\` — project directories
- `C:\Users\<your-username>\configs\` — config files
- `C:\Users\<your-username>\logs\` — log files

### 2. Docker volumes (already in `docker-compose.yml`)
```yaml
volumes:
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/projects:/projects:ro
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/configs:/configs:ro
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/logs:/logs:ro
  - ./mcpo/config.json:/config/config.json:ro
```

### 3. Recreate mcpo to pick up config
```bash
docker compose up -d --force-recreate mcpo
```

### 4. Add tools in Open WebUI
1. Admin Panel → Settings → Integrations → External Tool Servers
2. Add OpenAPI server:
   - Name: `projects_ops`
   - URL: `http://mcpo:8000/projects_ops`
3. Enable in chat sessions

### 5. Test (CLI)
```bash
# Verify mcpo sees tools
curl -s http://localhost:8000/openapi.json | grep projects_ops

# Test file access
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "", "file_path": "README.md", "base_dir": "/projects"}'
```

---

## Security Features (All Active)

- Path traversal protection
- Sensitive file filtering (`.env`, keys, certs)
- File size limits (32KB read)
- Directory exclusion (`.git`, `node_modules`, etc.)
- Read-only access (no writes)
- All services bind to localhost

---

## File Access Permissions

| Tool | Directories | Access | Size Limits |
|------|-------------|--------|-------------|
| filesystem | /workspace | R/W | 32KB read, 1MB write |
| projects_ops | /projects, /configs | Read-only | 32KB read |
| local_ops | /repo, /data, /workspace | Read-only | 32KB read |
| agent_cli.py | --repo directory | Conditional | 32KB read, 1MB write |

---

## Troubleshooting

### mcpo doesn't see new tools
```bash
docker compose restart mcpo
docker logs mcpo
```

### Projects directory not accessible
```bash
docker exec mcpo ls -la /projects
ls -la ~/projects
```

### Authentication proxy fails (if enabled)
```bash
docker exec auth_proxy cat /etc/caddy/Caddyfile
docker exec auth_proxy env | grep ADMIN
docker logs auth_proxy
```

---

## Rollback
```bash
# Comment out volume mounts in docker-compose.yml
# Remove projects_ops from mcpo/config.json
docker compose restart mcpo
```