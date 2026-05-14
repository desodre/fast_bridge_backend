# Fast Bridge Backend — Project Context

## Project Overview
**Fast Bridge Backend** is a specialized control layer for Android devices, exposing them as manageable resources via HTTP REST, WebSocket, and the **Model Context Protocol (MCP)**. It enables remote interaction including screen capture, UI hierarchy inspection, shell command execution, and real-time video streaming with touch/keyboard control.

### Core Technologies
- **Language:** Python 3.12+ (managed via `uv`)
- **Framework:** FastAPI
- **Device Communication:** `adbutils`, `uiautomator2`
- **Video/Control:** `scrcpy` (custom server integration), `PyAV`
- **MCP:** `FastMCP` (via `mcp` package)
- **Logging:** `Loguru`
- **Models:** `Pydantic`

---

## Architecture & Conventions

### Directory Structure
- `app/`: Main application logic.
    - `interfaces/mcp/`: MCP server definition and tool registration.
    - `services/`: `DeviceService` handles core business logic.
    - `controller/`: Low-level control logic (scrcpy server management, binary touch protocols).
    - `routes/`: FastAPI routers for REST and WebSocket.
    - `model/`: Pydantic schemas and parsers.
    - `binaries/`: Contains `scrcpy-server-v2.7.jar`.
- `main.py`: Application entry point, CORS config, and MCP mounting.
- `mcp_entry.py`: (Optional) Entry point for MCP-only usage or testing.
- `tests/`: Pytest-based test suite with dependency overriding.

### Dependency Injection
The project follows a singleton-based dependency injection pattern:
1. `DeviceManager` (in `app/dependencies.py`) is a singleton.
2. `DeviceService` is instantiated per request, receiving the `DeviceManager`.
3. Routes receive `DeviceService` via `Depends(get_device_service)`.

### Logging
Always use `from app.core import log`. Never use `print()` or the standard `logging` module directly. Logs are configured with rotation and compression in the `logs/` directory.

---

## Building and Running

### Installation
The project uses `uv` for lightning-fast dependency management.
```bash
# Install dependencies
uv sync
```

### Running the Server
```bash
# Starts FastAPI on port 8000 and opens the web frontend
python main.py
```

### Testing
```bash
# Run all tests
pytest tests/
```

---

## MCP Integration
The backend serves as an MCP server, allowing LLMs (like Claude) to control Android devices directly.

- **Transport:** STDIO.
- **Claude Desktop Configuration:**
  ```json
  {
    "mcpServers": {
      "fast-bridge": {
        "command": "python",
        "args": ["mcp_entry.py"]
      }
    }
  }
  ```

### Available MCP Tools
- `list_connected_devices()`: Returns list of device serials.
- `get_ui_hierarchy(serial)`: Returns XML dump of the current screen.
- `take_screenshot(serial)`: Returns base64 JPEG of the screen.
- `execute_adb_command(serial, command)`: Executes authorized shell commands (e.g., `input`, `am`, `pm`).

---

## Development Guidelines
- **Adding Features:** New device capabilities should be added to `DeviceService` first, then exposed via REST/WebSocket/MCP.
- **Security:** `execute_adb_command` uses a strict whitelist and prevents shell injection. Always validate commands before execution.
- **Testing Changes:** When modifying API logic, update `tests/test_device_api.py` or add new tests ensuring that `get_device_service` dependency is correctly overridden for isolation.
- **Binary Protocols:** The `scrcpy` integration involves binary protocol serialization in `app/controller/touch_controller.py`. Consult the scrcpy documentation if modifying this layer.
