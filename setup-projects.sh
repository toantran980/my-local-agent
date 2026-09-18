#!/bin/bash
# Setup script for homelab project directories
# Run this in WSL2 Ubuntu

set -e  # Exit on error

echo "=== Homelab Project Directory Setup ==="

# Detect if we should use Linux or Windows filesystem
echo "Choose filesystem location:"
echo "1) Linux filesystem (${MY_LOCAL_AGENT_ROOT:-/home/$USER}/...) - Faster, WSL2 native"
echo "2) Windows filesystem (${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/...) - Slower, accessible from Windows"
read -p "Enter choice (1 or 2) [default: 1]: " choice
choice=${choice:-1}

if [ "$choice" = "2" ]; then
    BASE_DIR="${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}"
    echo "Using Windows filesystem: $BASE_DIR"
else
    BASE_DIR="${MY_LOCAL_AGENT_ROOT:-/home/$USER}"
    echo "Using Linux filesystem: $BASE_DIR"
fi

# Create directories
echo "Creating directories..."
mkdir -p "$BASE_DIR/projects"
mkdir -p "$BASE_DIR/configs"
mkdir -p "$BASE_DIR/logs"

# Add sample content for testing
echo "Adding sample content..."
echo "# Sample project directory" > "$BASE_DIR/projects/README.md"
echo "# Sample configuration file" > "$BASE_DIR/configs/example.conf"
echo "$(date): Setup script ran" > "$BASE_DIR/logs/setup.log"

echo ""
echo "✅ Directories created successfully:"
ls -la "$BASE_DIR/projects" "$BASE_DIR/configs" "$BASE_DIR/logs"

echo ""
echo "=== IMPORTANT ==="
if [ "$choice" = "2" ]; then
    echo "You chose Windows filesystem. Update docker-compose.yml:"
    echo "  - Comment out Linux paths (${MY_LOCAL_AGENT_ROOT:-/home/$USER}/...)"
    echo "  - Uncomment Windows paths (${MY_LOCAL_AGENT_ROOT:-/mnt/c/Users/$USER}/...)"
    echo ""
    echo "Then restart mcpo:"
    echo "  docker compose restart mcpo"
else
    echo "You chose Linux filesystem (current config is correct)."
    echo ""
    echo "Next steps:"
    echo "1. Navigate to your project directory:"
    echo "   cd ${MY_LOCAL_AGENT_ROOT:-$(pwd)}"
    echo ""
    echo "2. Restart mcpo service:"
    echo "   docker compose restart mcpo"
fi

echo ""
echo "3. Verify MCP tools are available:"
echo "   curl -s http://localhost:8000/openapi.json | python3 -c 'import json,sys; print(list(json.load(sys.stdin)[\"paths\"]))'"
echo ""
echo "4. Test projects_ops directly:"
echo "   ./test-projects-ops.sh"