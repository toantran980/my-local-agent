# projects_ops MCP — Usage Examples

The `projects_ops` MCP server provides read-only access to your project directories via structured tools.

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

- Path traversal blocked (paths resolved relative to base dir)
- Sensitive files blocked (`.env`, keys, certs, etc.)
- 32KB read limit per file
- Exclusions: `.git`, `node_modules`, `__pycache__`, `.venv`, etc.
- Read-only — no write capability
- All services bind to localhost only

---

## Troubleshooting

```bash
# Verify mcpo sees tools
curl -s http://localhost:8000/openapi.json | grep projects_ops

# Test file access
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "", "file_path": "README.md", "base_dir": "/projects"}'

# Check mount
docker exec mcpo ls -la /projects

# Check mcpo logs
docker logs mcpo --tail 20
```