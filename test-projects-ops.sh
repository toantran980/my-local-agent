#!/bin/bash
# Test script for projects_ops MCP server
# Run this after setup-projects.sh and restarting mcpo

set -e

echo "=== Testing projects_ops MCP Server ==="

# Check if mcpo is running
echo "1. Checking mcpo service status..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ mcpo is not running. Start it with: docker compose up -d mcpo"
    exit 1
fi
echo "✅ mcpo is running"

# Check available MCP tools
echo ""
echo "2. Checking available MCP tools..."
TOOLS=$(curl -s http://localhost:8000/openapi.json | python3 -c 'import json,sys; print(list(json.load(sys.stdin)["paths"]))' 2>/dev/null || echo "[]")
echo "Available tools: $TOOLS"

if [[ "$TOOLS" != *"/projects_ops"* ]]; then
    echo "❌ projects_ops not found in available tools"
    echo "Check mcpo config: docker exec mcpo cat /opt/mcpo/config.json"
    exit 1
fi
echo "✅ projects_ops is available"

# Check which filesystem is mounted
echo ""
echo "3. Checking mounted filesystem..."
MOUNT_INFO=$(docker inspect mcpo | grep -A 5 "projects" || echo "")
if [[ "$MOUNT_INFO" == *"/mnt/c"* ]]; then
    echo "📁 Windows filesystem mounted (/mnt/c/...)"
    BASE_DIR="/projects"  # Container path stays same
elif [[ "$MOUNT_INFO" == *"${MY_LOCAL_AGENT_ROOT:-/home/$USER}"* ]]; then
    echo "📁 Linux filesystem mounted (${MY_LOCAL_AGENT_ROOT:-/home/$USER}/...)"
    BASE_DIR="/projects"
else
    echo "⚠️  Could not determine mount type, testing default /projects"
    BASE_DIR="/projects"
fi

# Test list_projects endpoint
echo ""
echo "4. Testing list_projects endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/projects_ops/tools/list_projects \
  -H "Content-Type: application/json" \
  -d "{\"arguments\": {\"base_dir\": \"$BASE_DIR\"}}")

if [[ "$RESPONSE" == *"error"* ]] || [[ -z "$RESPONSE" ]]; then
    echo "❌ list_projects failed"
    echo "Response: $RESPONSE"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check if directories exist on host:"
    echo "   ls -la ${MY_LOCAL_AGENT_ROOT:-/home/$USER}/projects  # or ${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/projects"
    echo "2. Check docker mounts:"
    echo "   docker inspect mcpo | grep -A 10 mounts"
    echo "3. Check container paths:"
    echo "   docker exec mcpo ls -la /projects"
    exit 1
fi
echo "✅ list_projects works"
echo "Response: $RESPONSE"

# Test project structure endpoint
echo ""
echo "5. Testing get_project_structure endpoint..."
STRUCTURE=$(curl -s -X POST http://localhost:8000/projects_ops/tools/get_project_structure \
  -H "Content-Type: application/json" \
  -d "{\"arguments\": {\"project\": \"\", \"base_dir\": \"$BASE_DIR\"}}")

if [[ "$STRUCTURE" == *"error"* ]]; then
    echo "⚠️  get_project_structure returned error (expected if projects dir is empty)"
else
    echo "✅ get_project_structure works"
    echo "Response: $STRUCTURE"
fi

# Test local_ops for projects overview
echo ""
echo "6. Testing local_ops projects_overview..."
PROJECTS=$(curl -s -X POST http://localhost:8000/local_ops/tools/projects_overview \
  -H "Content-Type: application/json" \
  -d '{}')

if [[ "$PROJECTS" == *"not found"* ]]; then
    echo "⚠️  projects directory not mounted yet"
    echo "Check docker volume mounts: docker inspect mcpo | grep -A 10 mounts"
else
    echo "✅ projects_overview works"
    echo "Response: $PROJECTS"
fi

echo ""
echo "=== Test Summary ==="
echo "✅ Basic tests passed"
echo ""
echo "Next steps:"
echo "1. Add projects_ops tool in Open WebUI (http://localhost:3000)"
echo "2. Admin Panel → Settings → Integrations → External Tool Servers"
echo "3. Add OpenAPI server: Name 'projects_ops', URL 'http://mcpo:8000/projects_ops'"
echo "4. Enable the tool in chat sessions"