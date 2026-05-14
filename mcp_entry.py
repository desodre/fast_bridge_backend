"""
Entrypoint MCP — Fast Bridge (stdio)
=====================================
Inicia o servidor MCP usando o transporte stdio, compatível com
Claude Desktop e qualquer cliente MCP padrão.

Configuração no Claude Desktop:
    {
      "mcpServers": {
        "fast-bridge": {
          "command": "python",
          "args": ["mcp_entry.py"]
        }
      }
    }

Uso direto:
    python mcp_entry.py
"""

import app.interfaces.mcp.tools  # noqa: F401 — registra as ferramentas no servidor MCP
from app.interfaces.mcp.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
