from app.routes.device import router as device_router
from app.routes.health import health_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import webbrowser
import uvicorn

import app.interfaces.mcp.tools  # noqa: F401 — registra as ferramentas no servidor MCP
from app.interfaces.mcp.server import mcp

app = FastAPI(title='Fast Bridge API', description='API para controle de dispositivos Android via ADB e uiautomator2', version='1.0.0')
app.include_router(device_router)
app.include_router(health_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://fast-bridge-nine.vercel.app'],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT'],
    allow_headers=['*'],
)

# Servidor MCP montado como sub-aplicação ASGI.
# Acessível em http://localhost:8000/mcp (Streamable HTTP transport).
# Claude Desktop config: { "url": "http://localhost:8000/mcp" }
app.mount("/mcp", mcp.streamable_http_app())

if __name__ == '__main__':
    print("Access https://fast-bridge-nine.vercel.app to get started")
    webbrowser.open('https://fast-bridge-nine.vercel.app')
    uvicorn.run(app, port=8000)

