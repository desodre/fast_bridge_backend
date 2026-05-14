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

import asyncio

import app.interfaces.mcp.tools  # noqa: F401 — registra as ferramentas no servidor MCP
from app.interfaces.mcp.server import mcp

if __name__ == "__main__":
    async def main() -> None:
        """Inicia o servidor MCP usando o transporte stdio."""
        await mcp.run_stdio_async()
    asyncio.run(main())
