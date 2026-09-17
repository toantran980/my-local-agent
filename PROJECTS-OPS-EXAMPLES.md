# projects_ops Usage Examples

This guide shows how to use the projects_ops MCP server for various project analysis tasks.

## Prerequisites

- Docker Desktop running with services started
- projects_ops MCP server configured in Open WebUI
- Projects in `/mnt/c/Users/toant/projects/` directory

## Sample Projects Created

Three sample projects have been created for testing:

1. **web-app/** - React/Node.js web application
2. **backend-api/** - RESTful API service  
3. **data-pipeline/** - ETL data processing pipeline

## Open WebUI Configuration

1. Open http://localhost:3000
2. Go to **Admin Panel → Settings → Integrations → External Tool Servers**
3. Add new OpenAPI server:
   - Name: `projects_ops`
   - URL: `http://mcpo:8000/projects_ops`
4. Enable the tool in chat sessions (click tools icon in top-right)

## Usage Examples

### 1. List Available Projects

**Prompt:**
```
Use the projects_ops tool to list all available projects in /projects
```

**Expected Result:**
- Returns: web-app, backend-api, data-pipeline

### 2. Analyze Project Structure

**Prompt:**
```
Use projects_ops to get the structure of the web-app project
```

**Expected Result:**
- Tree view showing directories and files in web-app/
- Helps understand project layout before deep analysis

### 3. Read Configuration Files

**Prompt:**
```
Use projects_ops to read the package.json file from the web-app project
```

**Expected Result:**
- Returns the package.json content
- Shows dependencies, scripts, and project metadata

### 4. Search Across Projects

**Prompt:**
```
Use projects_ops to search for "TODO" comments across all projects
```

**Expected Result:**
- Lists files containing TODO comments
- Shows line numbers and context

### 5. Code Review - Web Application

**Prompt:**
```
Use projects_ops to read the src/index.js file from web-app and review the code for best practices
```

**Expected Result:**
- Code analysis of the Express.js server
- Suggestions for improvements

### 6. API Documentation Review

**Prompt:**
```
Use projects_ops to read the server.js from backend-api and document the API endpoints
```

**Expected Result:**
- Documentation of API endpoints
- Analysis of the Express.js API structure

### 7. Data Pipeline Analysis

**Prompt:**
```
Use projects_ops to read the pipeline.py from data-pipeline and analyze the ETL workflow
```

**Expected Result:**
- Analysis of the data processing pipeline
- Suggestions for optimization

### 8. Cross-Project Dependency Analysis

**Prompt:**
```
Use projects_ops to search for "import" or "require" statements across all projects to understand dependencies
```

**Expected Result:**
- Lists all import/require statements
- Shows dependency relationships between projects

### 9. Configuration Comparison

**Prompt:**
```
Use projects_ops to read the package.json from web-app and compare it with typical Node.js project structures
```

**Expected Result:**
- Analysis of project configuration
- Comparison with standard patterns

### 10. Security Review

**Prompt:**
```
Use projects_ops to search for potential security issues like hardcoded passwords or API keys across all projects
```

**Expected Result:**
- Security analysis of codebase
- Identification of potential vulnerabilities

## CLI Testing Examples

When Docker is running, you can test directly via CLI:

```bash
# List projects
curl -X POST http://localhost:8000/projects_ops/list_projects \
  -H "Content-Type: application/json" \
  -d '{"base_dir": "/projects"}'

# Get project structure
curl -X POST http://localhost:8000/projects_ops/get_project_structure \
  -H "Content-Type: application/json" \
  -d '{"project": "web-app", "base_dir": "/projects"}'

# Read a file
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "web-app", "file_path": "README.md", "base_dir": "/projects"}'

# Search across projects
curl -X POST http://localhost:8000/projects_ops/search_projects \
  -H "Content-Type: application/json" \
  -d '{"pattern": "TODO", "base_dir": "/projects"}'

# List files in a project
curl -X POST http://localhost:8000/projects_ops/list_project_files \
  -H "Content-Type: application/json" \
  -d '{"project": "web-app", "base_dir": "/projects"}'
```

## Project-Specific Examples

### Web Application Development

**Code Review:**
```
Read the src/index.js from web-app and suggest improvements for error handling and logging
```

**Architecture Analysis:**
```
Get the structure of web-app and analyze the project architecture pattern
```

### Backend API Development

**API Documentation:**
```
Read the server.js from backend-api and generate API documentation
```

**Database Schema Analysis:**
```
Search for database models and schema definitions in backend-api
```

### Data Engineering

**Pipeline Review:**
```
Read the pipeline.py from data-pipeline and analyze the ETL workflow efficiency
```

**Error Handling:**
```
Search for error handling patterns in data-pipeline and suggest improvements
```

## Advanced Use Cases

### Multi-Project Refactoring

**Prompt:**
```
Analyze all three projects and suggest ways to improve code consistency and shared patterns
```

### Performance Analysis

**Prompt:**
```
Search for performance bottlenecks like nested loops or inefficient database queries across all projects
```

### Documentation Generation

**Prompt:**
```
Generate comprehensive documentation for the web-app project by reading all source files
```

### Code Quality Metrics

**Prompt:**
```
Analyze code quality across all projects by searching for anti-patterns and suggesting improvements
```

## Security Features

The projects_ops server includes several security features:

- **Path Traversal Protection**: Prevents access outside project directories
- **Sensitive File Filtering**: Blocks .env, keys, certificates
- **File Size Limits**: 32KB read limit prevents memory issues
- **Directory Exclusion**: Skips .git, node_modules, __pycache__

## Troubleshooting

### Projects Not Listed

**Problem:** list_projects returns "No projects found"

**Solution:**
- Verify directories exist: `ls -la /mnt/c/Users/toant/projects/`
- Check Docker mount: `docker exec mcpo ls -la /projects`
- Restart mcpo: `docker compose restart mcpo`

### File Read Errors

**Problem:** read_project_file returns "File not found"

**Solution:**
- Verify file path is correct
- Check if file is in excluded directory
- Ensure file is not a sensitive file (.env, keys)

### Search Returns No Results

**Problem:** search_projects returns "No matches found"

**Solution:**
- Verify search pattern is correct regex
- Check if files exist in projects
- Ensure files are not in excluded directories

## Next Steps

1. **Start Docker Desktop** to enable services
2. **Test CLI commands** to verify functionality
3. **Add to Open WebUI** for agent usage
4. **Populate with real projects** from your development work
5. **Create custom examples** based on your specific use cases

## Sample Project Locations

- **Web App:** `C:\Users\toant\projects\web-app\`
- **Backend API:** `C:\Users\toant\projects\backend-api\`
- **Data Pipeline:** `C:\Users\toant\projects\data-pipeline\`

These sample projects provide realistic scenarios for testing the projects_ops functionality with different types of development work.