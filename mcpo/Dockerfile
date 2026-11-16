FROM python:3.12-slim

# git: used by the self-authored local_ops MCP server (git_state tool).
# nodejs: the official filesystem MCP server is now a Node package
# (https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem);
# the old PyPI package (uvx mcp-server-filesystem) no longer exists.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git nodejs npm \
 && rm -rf /var/lib/apt/lists/*

# mcpo/requirements.txt contains the bridge and MCP server Python dependencies.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# filesystem server, installed globally at build time so startup is offline.
RUN npm install -g @modelcontextprotocol/server-filesystem

WORKDIR /config

COPY config.json ./config.json

EXPOSE 8000

CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--config", "/config/config.json"]