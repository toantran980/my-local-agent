"""projects_ops - MCP server for safe project directory access.

Provides controlled read-only access to project directories with security
constraints similar to agent_cli.py. Designed for homelab expansion while
maintaining safety boundaries.

Env overrides (defaults match the compose mounts):
  PROJECTS_DIR    project directory   (default /projects)
  CONFIGS_DIR     config files        (default /configs)
  MAX_FILE_BYTES  file read limit     (default 32000)
  MAX_RESULTS     search result limit (default 50)
"""

import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("projects-ops")

# Security constraints
SENSITIVE_FILE_NAMES = {
    ".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519",
    ".pem", ".key", ".p12", ".pfx"
}
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", "dist", "build"
}


def _env(key, default):
    return os.environ.get(key, default)


def _is_sensitive_path(path: Path) -> bool:
    """Check if path is sensitive (credentials, keys, etc.)."""
    name = path.name.lower()
    if name in SENSITIVE_FILE_NAMES:
        return True
    if name.startswith(".env") and name != ".env.example":
        return True
    return name.endswith((".pem", ".key", ".p12", ".pfx"))


def _is_excluded_dir(path: Path) -> bool:
    """Check if path is in an excluded directory."""
    return any(part in EXCLUDED_DIRS for part in path.parts)


@mcp.tool()
def list_projects(base_dir: str = "/projects") -> str:
    """List all project directories in the base directory.
    
    Returns only directory names, not contents. Safe for exploration.
    """
    d = Path(base_dir)
    if not d.is_dir():
        return f"Directory does not exist: {base_dir}"
    
    projects = []
    for item in d.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            projects.append(item.name)
    
    if not projects:
        return f"No projects found in {base_dir}"
    
    return "\n".join(sorted(projects))


@mcp.tool()
def read_project_file(
    project: str,
    file_path: str,
    base_dir: str = "/projects",
    max_bytes: int = 32000
) -> str:
    """Read a file from a specific project directory.
    
    Security features:
    - Path resolution prevents directory traversal
    - Sensitive files are blocked
    - File size is limited
    - Only reads from specified project directory
    
    Args:
        project: Project directory name
        file_path: Relative path within the project
        base_dir: Base projects directory (default /projects)
        max_bytes: Maximum bytes to read (default 32000)
    """
    max_bytes = int(_env("MAX_FILE_BYTES", max_bytes))
    
    # Resolve path safely
    base = Path(base_dir)
    project_path = base / project
    
    if not project_path.is_dir():
        return f"Project directory not found: {project}"
    
    # Prevent directory traversal
    target = (project_path / file_path).resolve()
    if not str(target).startswith(str(project_path)):
        return "ERROR: Path escapes project directory"
    
    # Security checks
    if _is_sensitive_path(target):
        return "ERROR: Access to sensitive file is denied"
    if _is_excluded_dir(target):
        return "ERROR: Access to excluded directory is denied"
    
    if not target.is_file():
        return f"File not found: {file_path}"
    
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_bytes:
            return content[:max_bytes] + f"\n... (truncated at {max_bytes} bytes)"
        return content
    except (OSError, UnicodeDecodeError) as e:
        return f"ERROR reading file: {e}"


@mcp.tool()
def search_projects(
    pattern: str,
    base_dir: str = "/projects",
    file_pattern: str = "*",
    max_results: int = 50
) -> str:
    """Search for a regex pattern across all project files.
    
    Security features:
    - Only searches in allowed directories
    - Sensitive files are skipped
    - Excluded directories are skipped
    - Result count is limited
    
    Args:
        pattern: Regular expression pattern to search
        base_dir: Base projects directory (default /projects)
        file_pattern: Glob pattern for files (default *)
        max_results: Maximum results to return (default 50)
    """
    max_results = int(_env("MAX_RESULTS", max_results))
    
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"ERROR: Invalid regex pattern: {e}"
    
    base = Path(base_dir)
    if not base.is_dir():
        return f"Directory does not exist: {base_dir}"
    
    matches = []
    for path in base.rglob(file_pattern):
        if not path.is_file():
            continue
        
        # Security checks
        if _is_sensitive_path(path) or _is_excluded_dir(path):
            continue
        
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if regex.search(content):
                rel_path = path.relative_to(base)
                matches.append(str(rel_path))
                if len(matches) >= max_results:
                    break
        except (OSError, UnicodeDecodeError):
            continue
    
    if not matches:
        return "No matches found"
    
    return "\n".join(matches)


@mcp.tool()
def list_project_files(
    project: str,
    base_dir: str = "/projects",
    max_files: int = 30
) -> str:
    """List files in a specific project directory.
    
    Returns relative file paths with size information.
    Skips sensitive files and excluded directories.
    
    Args:
        project: Project directory name
        base_dir: Base projects directory (default /projects)
        max_files: Maximum files to list (default 30)
    """
    max_files = int(_env("MAX_RESULTS", max_files))
    
    base = Path(base_dir)
    project_path = base / project
    
    if not project_path.is_dir():
        return f"Project directory not found: {project}"
    
    files = []
    for path in project_path.rglob("*"):
        if not path.is_file():
            continue
        
        # Security checks
        if _is_sensitive_path(path) or _is_excluded_dir(path):
            continue
        
        rel_path = path.relative_to(project_path)
        size = path.stat().st_size
        files.append(f"{rel_path}  ({size} bytes)")
        
        if len(files) >= max_files:
            break
    
    if not files:
        return f"No files found in project {project}"
    
    return "\n".join(files)


@mcp.tool()
def get_project_structure(
    project: str,
    base_dir: str = "/projects",
    max_depth: int = 3
) -> str:
    """Get directory structure of a project.
    
    Returns a tree-like structure showing directories and key files.
    Useful for understanding project layout before deep inspection.
    
    Args:
        project: Project directory name
        base_dir: Base projects directory (default /projects)
        max_depth: Maximum directory depth to explore (default 3)
    """
    base = Path(base_dir)
    project_path = base / project
    
    if not project_path.is_dir():
        return f"Project directory not found: {project}"
    
    def build_tree(path: Path, depth: int, prefix: str = "") -> list[str]:
        if depth > max_depth or not path.is_dir():
            return []
        
        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for i, item in enumerate(items):
                # Skip hidden files and excluded dirs
                if item.name.startswith('.') or _is_excluded_dir(item):
                    continue
                
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{item.name}")
                
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(item, depth + 1, prefix + extension))
        except PermissionError:
            lines.append(f"{prefix}[permission denied]")
        
        return lines
    
    tree_lines = [f"Project structure for {project}:"]
    tree_lines.extend(build_tree(project_path, 0))
    
    if len(tree_lines) == 1:
        return f"Project {project} is empty or inaccessible"
    
    return "\n".join(tree_lines)


if __name__ == "__main__":
    mcp.run()