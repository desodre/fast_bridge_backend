# Fast Bridge Backend — Copilot Instructions

## Project Overview

FastAPI + WebSocket backend that exposes Android devices connected via USB (ADB) as HTTP and WebSocket resources. Enables screenshots, shell commands, touch/key input, and real-time video streaming via scrcpy.

**Runtime requirements:** Python 3.10+, ADB in PATH, Android device with USB debugging, `app/binaries/scrcpy-server-v2.7.jar` present.

---

## Commands

```bash
# Run the server
python main.py
# Server starts at http://localhost:8000, Swagger UI at /docs

# Run all tests
pytest tests/

# Run a single test
pytest tests/test_device_api.py::test_send_adb_shell_success

# Install dependencies
pip install -r requirements.txt
```

---

## Architecture

```
main.py                   # FastAPI app, CORS middleware, Uvicorn entrypoint
app/
  dependencies.py         # DeviceManager class + get_device_manager() DI provider
  routes/
    device.py             # Thin REST + WebSocket endpoints (use DeviceService via Depends)
    health.py             # GET /health
  services/
    device_service.py     # DeviceService: all business logic; get_device_service() provider
  controller/
    scrcpy.py             # ScrcpyServer: pushes JAR, opens sockets, video stream + WS control
    touch_controller.py   # Serializes touch/key events into scrcpy binary protocol
    android_input.py      # KeyeventAction and MetaState enums
    keycode.py            # KeyCode enum (all Android keycodes)
    file_manager.py       # ls -la wrapper → returns FileManagerResponse
  model/
    adboutput.py          # AdbResponse Pydantic model
    file_entry.py         # FileEntry, FileManagerResponse + parse_ls_output()
  core/
    constants.py          # Global constants (PORT)
    logger_config.py      # Loguru setup; exports `log`
  binaries/
    scrcpy-server-v*.jar  # scrcpy server JAR(s)
```

### Device connection lifecycle

`app/dependencies.py` expõe `DeviceManager` — um singleton que mantém conexões `uiautomator2.Device` por serial. Injetado via `Depends(get_device_manager)`. `DeviceService` recebe o manager e encapsula toda lógica de negócio; as rotas apenas chamam o serviço.

```python
# padrão de injeção nas rotas
@router.get("/device/{serial}/screenshot")
def screenshot(serial: str, svc: DeviceService = Depends(get_device_service)):
    return svc.screenshot(serial)
```

### WebSocket video+control flow

`WS /ws/device/{serial}/control` → `ScrcpyServer.handle_unified_websocket()` runs two concurrent asyncio tasks:
- `_stream_video_to_websocket`: reads raw H.264 from scrcpy socket, decodes with PyAV, sends JPEG frames as binary WS messages.
- `_handle_control_websocket`: receives JSON from client, dispatches to `ScrcpyTouchController` (binary protocol) or `device.shell()`.

`ScrcpyServer.__init__` opens **three** socket connections to the device: one shell connection (to run the JAR), one video socket, one control socket.

### Device connection cache

`app/routes/device.py` keeps a module-level `_connected_devices: dict` that maps device serials to `uiautomator2.Device` instances. The `get_cached_device()` helper is used by all REST endpoints to avoid reconnecting on every request. The WebSocket endpoint bypasses this cache and uses `adbutils.device()` directly.

---

## Key Conventions

- **Error status code for ADB failures is `505`** (not `500`). All ADB-related exceptions raise `HTTPException(status_code=505)`.
- **Logging** uses Loguru via `from ..core import log` (or `from app.core import log`). Do not use `print()` or `logging.getLogger()` in `app/` code — the scrcpy module is the one exception (it uses stdlib `logging`).
- **Pydantic v2** is in use (`pydantic==2.12.5`). Use `model_config`, `model_validate`, etc., not v1 APIs.
- **Touch coordinates in WS messages are percentages** (`xP`, `yP` in range 0.0–1.0). The controller converts to absolute pixels using `resolution_width`/`resolution_height` parsed from the scrcpy handshake.
- **Text input via WebSocket** uses Android broadcast (`am broadcast -a SONIC_KEYBOARD --es msg '...'`), not the scrcpy binary text protocol (which is a stub/`pass`).
- **Tests mock at the boundary**: `adbutils.adb.device_list` is patched for device listing; `app.routes.device.get_cached_device` is patched for all device-specific endpoint tests. Tests use `fastapi.testclient.TestClient` with `unittest.mock`.
- **CORS** is restricted to `https://fast-bridge-nine.vercel.app`. When adding new routes, only `GET` and `POST` methods are allowed by the current middleware config.
- **Tests use `app.dependency_overrides`** to inject mock services — never patch `get_cached_device` (removed). Pattern:
  ```python
  app.dependency_overrides[get_device_service] = lambda: DeviceService(_make_mock_manager(mock_device))
  # ... test ...
  app.dependency_overrides.pop(get_device_service, None)
  ```
- **`FileManagerResponse`** is the return type of `GET /device/{serial}/file_manager`. Parser lives in `app/model/file_entry.py::parse_ls_output()`, which handles regular files, directories, and symlinks from `ls -la` output.
