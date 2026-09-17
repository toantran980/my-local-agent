# Quickstart — start the whole stack from WSL2

This is the 60-second version of README.md. Copy the commands verbatim —
every file name below matches what is actually in this repo.

> You need: Docker Desktop **running** with the **WSL2 backend**, and the
> `wsl` command available from a Windows PowerShell/CMD prompt. Everything else
> is given to you by the compose file.

---

## 1. One command to start everything

    wsl bash -lc 'cd /mnt/c/Users/toant/Desktop/my-local-agent && docker compose up -d --build'

This starts three containers + pulls a model the first time:

| Service    | Purpose              | Address        |
| ---------- | -------------------- | -------------- |
| Ollama     | Local model runtime  | :11434 / UI    |
| mcpo       | MCP bridge (3 tools) | :8000          |
| Open WebUI | Chat UI              | :3000          |

First run does a one-time model pull (~5–6 GB). Later runs are instant.

---

## 2. Verify it is actually working

    wsl bash -lc 'cd /mnt/c/Users/toant/Desktop/my-local-agent && bash scripts/smoke-test.sh'

Expect: `SMOKE: PASS` and a GPU row `qwen3:8b  … VRAM …` (proof it's on the
RTX 5080, not CPU).

---

## 3. Talk to it

    # Open WebUI chat UI
    start http://localhost:3000

    # or from a Windows terminal via the OpenAI-compatible API
    curl -s http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" `
      -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Say hello to local agent"}]}' |
      python -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"

---

## 4. Scheduled night agent (the "works while you sleep" part)

The stack includes a real nightly agent: a Python triage job that inspects the
repo + GPU and writes a dated report.

    wsl bash -lc 'cd /mnt/c/Users/toant/Desktop/my-local-agent && bash scripts/install-cron.sh'

This installs a cron entry that runs the agent every day at **5:00 PM** (`0 17 * * *`). Grab the hourly override if you ever need a different one: `CRON_HOUR=17 CRON_MIN=0 ./scripts/install-cron.sh`.
Verify it landed:

    wsl crontab -l            # look for the "my-local-agent-nightly-triage" line

Reports appear in `reports/<YYYY-MM-DD>.md` each morning. To also get a draft
PR you approve, set `DRAFT_PR=1` with a `GH_REPO` when installing.

Run it once immediately (no cron needed) to prove it works:

    wsl bash -lc 'cd /mnt/c/Users/toant/Desktop/my-local-agent && python3 scripts/nightly-triage.py'

You should see a tool loop print (`git_status`, `gpu_status`, `models_list`,
`grep`, …) and a written `reports/<today>.md`.

---

## 5. Reliability harness (measure it, don't hope)

    wsl bash -lc 'cd /mnt/c/Users/toant/Desktop/my-local-agent && bash scripts/run-eval.sh && python3 scripts/eval-summary.py'

Expected result: `6/6 passed` and a pass-rate trend printed from
`eval/history.jsonl`. That number is the "reliability" answer for the project.

---

## 6. Health dashboard (optional)

If you have `wsl-vpnkit`-style setup or just want a plain HTTP check from
Windows:

    curl -s -o NUL -w "ollama %{http_code}  " http://localhost:11434
    curl -s -o NUL -w "mcpo %{http_code}  " http://localhost:8000
    curl -s -o NUL -w "webui %{http_code}`n" http://localhost:3000

Three 200s = everything is serving.

---

## Troubleshooting

| Symptom                              | Fix                                                                 |
| ------------------------------------ | ------------------------------------------------------------------- |
| `command not found: docker`           | Start **Docker Desktop** (it provides the docker CLI in WSL2)       |
| `connection refused: 11434`          | Containers not up yet → re-run step 1 and wait ~30 s for Ollama      |
| Smoke test "GPU" row missing/failing | Model not finished pulling → re-run step 1 once                     |
| WebUI won't load on :3000            | First cold start is slow; retry after ~1 min                        |
| Cron reports not appearing           | `wsl bash -lc 'service cron start'` then re-run `install-cron.sh`    |

All data stays local. Nothing in this file calls a cloud API.


## Homelab Setup (merged from HOMELAB-SETUP.md)

# Homelab Self-Hosted Agent Setup Guide

This guide explains the expanded setup for safe homelab deployment with controlled file access and future network capabilities.

## What's New

### 1. Safe Project Access (`projects_ops` MCP Server)
A new MCP server that provides secure, read-only access to your project directories with:
- Path traversal protection
- Sensitive file filtering (.env, keys, etc.)
- File size limits (32KB default)
- Directory exclusion (.git, node_modules, etc.)
- Structured project exploration tools

### 2. Enhanced Docker Configuration
- Commented volume mounts for project/configs directories
- Authentication proxy for future network access
- Security-first networking (localhost-only by default)

### 3. Authentication Layer
- Caddy-based authentication proxy
- Basic auth with configurable credentials
- TLS termination capability
- Health check endpoints

### 4. Expanded `local_ops` Tools
- `projects_overview()` - View available projects
- `configs_overview()` - View available config files  
- `system_status()` - Overall system health

## Setup Steps

### Phase 1: Enable Project Access ✅ COMPLETED

**Current Setup**: Windows filesystem paths for WSL2 compatibility

1. **Create directories on Windows host:**
```bash
# In WSL2 (runs setup script)
cd /mnt/c/Users/toant/Desktop/my-local-agent
chmod +x setup-projects.sh
./setup-projects.sh
# Choose option 2 (Windows filesystem)
```

This creates:
- `C:\Users\toant\projects\` - Your project directories
- `C:\Users\toant\configs\` - Configuration files
- `C:\Users\toant\logs\` - Log files for analysis

2. **Update docker-compose.yml volumes:**
Windows filesystem mounts are now active:
```yaml
volumes:
  # existing mounts...
  - /mnt/c/Users/toant/projects:/projects:ro
  - /mnt/c/Users/toant/configs:/configs:ro
  - /mnt/c/Users/toant/logs:/logs:ro
  - ./mcpo/config.json:/config/config.json:ro    # config mount
```

3. **Recreate the mcpo service:**
```bash
docker compose up -d --force-recreate mcpo
```

4. **Add tools in Open WebUI:**
1. Go to Admin Panel → Settings → Integrations → External Tool Servers
2. Add new OpenAPI server:
   - Name: `projects_ops`
   - URL: `http://mcpo:8000/projects_ops`
3. Enable the tool in chat sessions

5. **Test the setup (CLI):**
```bash
# Verify mcpo sees the new tools
curl -s http://localhost:8000/openapi.json

# Test file access
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "", "file_path": "README.md", "base_dir": "/projects"}'
```

### Phase 2: Enable vLLM (Optional, for Higher Throughput)

1. **Start vLLM service:**
```bash
docker compose --profile vllm up -d vllm
```

2. **Verify vLLM is running:**
```bash
curl -s http://localhost:8001/v1/models
# Should show Qwen3-14B-AWQ model
```

3. **Test inference:**
```bash
curl -s http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-14B-AWQ","messages":[{"role":"user","content":"1+1?"}],"stream":false}'
```

### Phase 3: Enable Network Access (When Ready)

1. **Set up authentication:**
```bash
# Copy the example config
cp auth-config.example .env

# Edit .env with your credentials
nano .env
# Set ADMIN_USER and ADMIN_PASSWORD
```

2. **Create Caddy directories:**
```bash
mkdir -p caddy/data caddy/config
```

3. **Enable authentication proxy:**
```bash
docker compose --profile auth up -d auth_proxy
```

4. **Test authentication:**
```bash
# Health check (no auth required)
curl http://localhost:8443/health

# Test authenticated access
curl -u admin:changeme http://localhost:8443/v1/models
```

5. **Enable LAN access (optional):**
Uncomment the LAN port in docker-compose.yml:
```yaml
ports:
  - "127.0.0.1:8443:443"      # local access
  - "192.168.1.100:8443:443"  # LAN access (uncomment)
```

## Usage Examples

### Using projects_ops in Open WebUI

1. **List available projects:**
```
Use the projects_ops tool to list_projects in /projects
```

2. **Explore project structure:**
```
Use projects_ops to get_project_structure for project "myapp" in /projects
```

3. **Read a specific file:**
```
Use projects_ops to read_project_file from project "myapp", file "src/main.py"
```

4. **Search across projects:**
```
Use projects_ops to search_projects for pattern "TODO" in /projects
```

### Using enhanced local_ops tools

1. **Check system status:**
```
Use local_ops to get system_status
```

2. **View available projects:**
```
Use local_ops to get projects_overview
```

3. **Monitor GPU usage:**
```
Use local_ops to get gpu_status
```

## Security Features

### Path Safety
- All paths are resolved relative to configured base directories
- Directory traversal attacks are prevented
- Symbolic links are not followed outside allowed directories

### File Protection
- Sensitive files (.env, keys, certificates) are blocked
- File size limits prevent memory issues
- Binary files are handled safely with error catching

### Network Security
- All services bind to localhost by default
- Authentication required for network access
- TLS termination for encrypted connections
- No API keys or secrets in logs

### Audit Trail
- All tool calls are logged by mcpo
- Open WebUI maintains conversation history
- Your existing audit system (.agent/audit/) continues to work

## File Access Permissions

| Tool | Directories | Access Type | Size Limits |
|------|-------------|-------------|-------------|
| filesystem | /workspace | Read/Write | 32KB read, 1MB write |
| projects_ops | /projects, /configs | Read-only | 32KB read |
| local_ops | /repo, /data, /workspace | Read-only | 32KB read |
| agent_cli.py | --repo directory | Conditional | 32KB read, 1MB write |

## Troubleshooting

### mcpo doesn't see new tools
```bash
# Restart mcpo to pick up config changes
docker compose restart mcpo

# Check mcpo logs
docker logs mcpo
```

### Projects directory not accessible
```bash
# Verify mount exists in container
docker exec mcpo ls -la /projects

# Check host directory exists
ls -la ~/projects
```

### Authentication proxy fails
```bash
# Check Caddy configuration
docker exec auth_proxy cat /etc/caddy/Caddyfile

# Verify environment variables
docker exec auth_proxy env | grep ADMIN

# Check Caddy logs
docker logs auth_proxy
```

### vLLM not loading model
```bash
# Check GPU is accessible
docker exec local_vllm nvidia-smi

# Verify model download
docker exec local_vllm ls -la /root/.cache/huggingface

# Check vLLM logs for errors
docker logs local_vllm
```

## Monitoring

### Resource Usage
```bash
# Check all services
docker compose ps

# Monitor GPU usage
docker exec local_ollama ollama ps

# Check disk usage
docker system df
```

### Logs
```bash
# Service logs
docker compose logs -f mcpo
docker compose logs -f local_ollama
docker compose logs -f open-webui

# Authentication proxy logs
docker logs auth_proxy
```

## Next Steps

1. **Populate your projects directory** with code you want the agent to analyze
2. **Configure Open WebUI** to use the new projects_ops tools
3. **Test with safe operations** (read-only, file exploration)
4. **Enable vLLM** if you need higher throughput
5. **Set up authentication** when ready for network access
6. **Consider Tailscale** for secure remote access (as mentioned in main README)

## Multimodal Transformation Roadmap

### Current State
- **Text-only processing**: Qwen3 models handle text input/output
- **Tool-based**: Agent uses filesystem tools, not direct image processing
- **RTX 5080**: Capable GPU for vision model inference

### Vision Model Options for Local Deployment

#### 1. Qwen2-VL / Qwen2.5-VL (Recommended)
- **Pros**: Native Qwen ecosystem, excellent vision-language performance
- **Model sizes**: 2B, 7B, 15B parameters (7B fits well on 16GB VRAM)
- **Hardware**: Qwen2-VL-7B ~14GB VRAM with image input
- **Integration**: OpenAI-compatible API possible via vLLM

#### 2. LLaVA (Large Language-and-Vision Assistant)
- **Pros**: Open-source, active community, multiple model variants
- **Model sizes**: 1.5B, 7B, 13B, 34B
- **Hardware**: LLaVA-7B ~12GB VRAM
- **Integration**: Available via Ollama and vLLM

#### 3. CLIP + Text Model Hybrid
- **Pros**: Lightweight, modular approach
- **Model sizes**: CLIP ViT-B/32 (~400MB) + text model
- **Hardware**: Very VRAM-efficient
- **Integration**: Custom pipeline, more complex setup

### Implementation Phases

#### Phase 1: Basic Image Input (Current Setup + Simple Integration)
**Goal**: Enable agent to process images with minimal changes

**Approach**:
1. Add image input capability to `agent_cli.py`
2. Use base64 encoding for image transmission
3. Deploy Qwen2-VL-7B via vLLM
4. Update tool schemas to accept image inputs

**Code Changes**:
```python
# agent_cli.py additions
def encode_image(image_path: Path) -> str:
    """Encode image as base64 for vision model."""
    import base64
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# Update tool definitions
def tool_definitions(mode: str) -> list[dict[str, Any]]:
    tools = existing_tools
    if mode == "agent":
        tools.append({
            "type": "function",
            "function": {
                "name": "analyze_image",
                "description": "Analyze an image file using vision model",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string"},
                        "question": {"type": "string"}
                    },
                    "required": ["image_path"]
                }
            }
        })
    return tools
```

**Docker Compose Addition**:
```yaml
vision_vllm:
  image: vllm/vllm-openai:latest
  container_name: vision_vllm
  profiles: ["vision"]
  restart: unless-stopped
  ports:
    - "127.0.0.1:8002:8000"
  volumes:
    - vision_cache:/root/.cache/huggingface
  environment:
    - VLLM_DISABLED_KERNELS=CutlassFp8BlockScaledMMKernel
  command:
    - --model
    - Qwen/Qwen2-VL-7B-Instruct
    - --max-model-len
    - "8192"
    - --gpu-memory-utilization
    - "0.85"
    - --max-num-seqs
    - "2"
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

#### Phase 2: Specialized Vision Tools
**Goal**: Add domain-specific image processing capabilities

**New MCP Server** (`mcp/vision_ops.py`):
```python
"""vision_ops - MCP server for image processing operations."""

from mcp.server.fastmcp import FastMCP
from pathlib import Path
import base64

mcp = FastMCP("vision-ops")

@mcp.tool()
def screenshot_analysis(image_path: str, question: str = "Describe this screenshot") -> str:
    """Analyze a screenshot with specific focus areas.
    
    Use for UI debugging, error analysis, or documentation generation.
    """
    # Encode and send to vision model
    image_data = encode_image(Path(image_path))
    # Call vision model API
    return f"Analysis of {image_path}: {question}"

@mcp.tool()
def document_ocr(image_path: str) -> str:
    """Extract text from document images using OCR.
    
    Useful for processing scanned documents, screenshots of text, etc.
    """
    # Integrate with Tesseract or similar
    pass

@mcp.tool()
def code_screenshot_explainer(image_path: str) -> str:
    """Explain code shown in a screenshot.
    
    Specialized prompt for code-related images.
    """
    pass

@mcp.tool()
def diagram_understanding(image_path: str) -> str:
    """Understand and describe technical diagrams.
    
    For architecture diagrams, flowcharts, network topologies, etc.
    """
    pass
```

#### Phase 3: Multimodal Agent Orchestration
**Goal**: Intelligent routing between text and vision models

**Router Logic**:
```python
class MultimodalRouter:
    def __init__(self):
        self.text_model = "qwen3:8b"
        self.vision_model = "Qwen/Qwen2-VL-7B-Instruct"
    
    def route_request(self, user_input: str, has_image: bool = False) -> str:
        if has_image or self.detect_image_reference(user_input):
            return self.vision_model
        return self.text_model
    
    def detect_image_reference(self, text: str) -> bool:
        """Detect if user is referring to an image."""
        image_keywords = ["screenshot", "image", "picture", "photo", "diagram"]
        return any(keyword in text.lower() for keyword in image_keywords)
```

### Hardware Requirements for Multimodal

| Model | Parameters | VRAM (no image) | VRAM (with image) | Recommended |
|-------|-----------|-----------------|------------------|-------------|
| Qwen2-VL-2B | 2B | ~4GB | ~6GB | Testing/Low VRAM |
| Qwen2-VL-7B | 7B | ~14GB | ~16GB | **Production** |
| Qwen2-VL-15B | 15B | ~22GB | ~24GB | Not for 16GB cards |
| LLaVA-7B | 7B | ~12GB | ~14GB | Alternative |

**Your RTX 5080 (16GB)**: Perfect for Qwen2-VL-7B with image input

### Security Considerations for Vision

1. **Image Sanitization**
   - File size limits (prevent DoS via large images)
   - Format validation (only allow PNG, JPG, WebP)
   - Resolution limits (max 4096x4096)

2. **Content Filtering**
   - Prevent processing of sensitive images (documents with PII)
   - Block malicious image formats
   - Audit log of all image processing

3. **Path Restrictions**
   - Apply same path traversal protection as text files
   - Restrict to allowed directories only
   - No network image fetching (local files only)

### Use Cases for Multimodal

1. **Code Analysis**
   - Screenshot debugging: "What's wrong with this error message?"
   - UI testing: "Does this match the design mockup?"
   - Documentation: "Generate docs from this screenshot"

2. **System Administration**
   - Log analysis: "Explain this error screenshot"
   - Dashboard monitoring: "Analyze this graph anomaly"
   - Configuration: "Compare these two config screenshots"

3. **Development Workflow**
   - Code review: "Review this code screenshot"
   - Architecture: "Explain this diagram"
   - Testing: "Does this output look correct?"

### Integration with Current Setup

**Minimal Changes Required**:
1. Add vision model service (docker compose profile)
2. Update `agent_cli.py` to handle image inputs
3. Add `vision_ops` MCP server
4. Update Open WebUI tool configuration

**Backward Compatibility**:
- Text-only mode remains default
- Vision features opt-in via profile
- Existing tools unchanged
- Same security model applies

### Testing Multimodal Capabilities

```bash
# Start vision model
docker compose --profile vision up -d vision_vllm

# Test image analysis
curl -X POST http://localhost:8002/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2-VL-7B-Instruct",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "Describe this image"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
      ]
    }],
    "max_tokens": 512
  }'
```

### Performance Optimization

1. **Image Preprocessing**
   - Resize large images before encoding
   - Use efficient compression (WebP)
   - Cache processed images

2. **Model Optimization**
   - Use quantized vision models (AWQ, GPTQ)
   - Batch multiple images when possible
   - Warm up model before first use

3. **Resource Management**
   - Limit concurrent image processing
   - Monitor VRAM usage during image input
   - Fallback to text-only if VRAM constrained

### Cost/Benefit Analysis

**Benefits**:
- Natural screenshot analysis for debugging
- UI/UX testing capabilities
- Document processing automation
- Enhanced code review workflows

**Costs**:
- Additional VRAM usage (~2-4GB with images)
- Increased inference latency
- More complex deployment
- Additional security considerations

**Recommendation**: Start with Phase 1, evaluate utility, then expand based on actual use cases.

### Future Enhancements

1. **Video Processing**
   - Frame extraction for video analysis
   - Temporal understanding for screen recordings

2. **Advanced Vision**
   - Object detection in screenshots
   - Layout analysis for UI components
   - OCR integration for text extraction

3. **Specialized Models**
   - Medical imaging (if applicable)
   - Technical diagram understanding
   - Handwriting recognition

## Rollback

If you need to revert changes:
```bash
# Comment out the new volume mounts in docker-compose.yml
# Remove projects_ops from mcpo/config.json
# Restart services
docker compose restart mcpo
```

The original setup remains fully functional without the homelab expansions.
