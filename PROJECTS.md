# Project Access via MCP (`projects_ops`)

A read-only MCP server providing secure, structured access to your project directories via structured tools.

---

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

## Available Tools

| Tool | Description |
|------|-------------|
| `list_projects()` | List all project directories in `/projects` |
| `get_project_structure(project, base_dir)` | Tree view of a project |
| `read_project_file(project, file_path, base_dir)` | Read a file's content |
| `search_projects(pattern, base_dir)` | Regex search across projects |
| `list_project_files(project, base_dir)` | List files in a project |

---

## CLI Examples (via mcpo OpenAPI)

### List projects
```bash
curl -X POST http://localhost:8000/projects_ops/list_projects \
  -H "Content-Type: application/json" \
  -d '{"base_dir": "/projects"}'
```

### Get project structure
```bash
curl -X POST http://localhost:8000/projects_ops/get_project_structure \
  -H "Content-Type: application/json" \
  -d '{"project": "myapp", "base_dir": "/projects"}'
```

### Read a file
```bash
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "myapp", "file_path": "src/main.py", "base_dir": "/projects"}'
```

### Search across projects
```bash
curl -X POST http://localhost:8000/projects_ops/search_projects \
  -H "Content-Type: application/json" \
  -d '{"pattern": "TODO|FIXME", "base_dir": "/projects"}'
```

### List project files
```bash
curl -X POST http://localhost:8000/projects_ops/list_project_files \
  -H "Content-Type: application/json" \
  -d '{"project": "myapp", "base_dir": "/projects"}'
```

---

## Open WebUI Integration

1. Admin Panel → Settings → Integrations → External Tool Servers
2. Add OpenAPI server:
   - Name: `projects_ops`
   - URL: `http://mcpo:8000/projects_ops`
3. Enable in chat sessions (top-right tools icon)

Then in chat:
```
Use projects_ops to list_projects in /projects
Use projects_ops to get_project_structure for project "myapp" in /projects
Use projects_ops to read_project_file from project "myapp", file "src/main.py"
Use projects_ops to search_projects for pattern "TODO" in /projects
```

---

## Project Directory Setup

```bash
# Create your projects (on Windows host)
mkdir -p ~/projects/myapp/src
echo "print('hello')" > ~/projects/myapp/src/main.py
echo "# My App" > ~/projects/myapp/README.md
```

Docker mounts `~/projects` → `/projects` (read-only) via compose:
```yaml
volumes:
  - ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/projects:/projects:ro
```

---

## Security (All Enforced)

- Path traversal blocked (paths resolved relative to base dirs)
- Sensitive files blocked (`.env`, keys, certs, etc.)
- 32KB read limit per file
- Exclusions: `.git`, `node_modules`, `__pycache__`, `.venv`, etc.
- Read-only — no write capability
- All services bind to localhost only

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

---

## Directory Structure (Created by setup-projects.sh)

```
C:\Users\<your-username>\
├── projects\        # Your project directories
├── configs\         # Configuration files
└── logs\            # Log files for analysis
```

Docker mounts these as `/projects`, `/configs`, `/logs` (read-only).