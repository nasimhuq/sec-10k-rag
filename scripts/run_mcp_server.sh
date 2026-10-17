#!/usr/bin/env bash
# Start Postgres, then the MCP server on stdio (for Claude Desktop).
# stdout is the MCP channel: everything else must go to stderr.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/snap/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$repo_root"
docker compose up --detach --wait db >&2
exec "$repo_root/.venv/bin/python" -m sec_10k_rag.step_08_mcp_server.run
