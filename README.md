# fast_bridge_backend

Backend da aplicação **Fast Bridge** — uma API REST, WebSocket e MCP para controle remoto de dispositivos Android via ADB e uiautomator2, com streaming de vídeo em tempo real via scrcpy.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Executando o Projeto](#executando-o-projeto)
- [Endpoints da API](#endpoints-da-api)
  - [Health](#health)
  - [Dispositivos](#dispositivos)
  - [Captura e Informações](#captura-e-informações)
  - [Gerenciador de Arquivos](#gerenciador-de-arquivos)
  - [Entrada (Input)](#entrada-input)
  - [Shell ADB](#shell-adb)
  - [WebSocket — Controle em Tempo Real](#websocket--controle-em-tempo-real)
- [Servidor MCP](#servidor-mcp)
- [Modelos de Dados](#modelos-de-dados)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Logging](#logging)
- [Frontend](#frontend)

---

## Visão Geral

O **Fast Bridge Backend** expõe dispositivos Android conectados via USB (ADB) como recursos HTTP, WebSocket e MCP. Com ele é possível:

- Listar dispositivos conectados
- Tirar screenshots
- Consultar propriedades do sistema e informações de tela
- Navegar no sistema de arquivos do dispositivo
- Executar comandos shell via ADB
- Enviar eventos de toque, teclas e texto
- Fazer streaming de vídeo e controlar o dispositivo em tempo real via WebSocket (protocolo scrcpy)
- Controlar dispositivos via LLMs usando o **Model Context Protocol (MCP)**

---

## Arquitetura

```
fast_bridge_backend/
├── main.py                        # Ponto de entrada — FastAPI + Uvicorn + montagem do MCP
├── mcp_server.py                  # Servidor MCP (FastMCP) com as 4 ferramentas de controle
├── pyproject.toml                 # Dependências gerenciadas via UV
├── app/
│   ├── dependencies.py            # DeviceManager singleton + get_device_manager()
│   ├── binaries/                  # scrcpy-server-v*.jar
│   ├── controller/
│   │   ├── scrcpy.py              # ScrcpyServer: streaming de vídeo + controle WebSocket
│   │   ├── touch_controller.py    # Protocolo binário de toque para scrcpy
│   │   ├── android_input.py       # Constantes de input Android (KeyeventAction, MetaState)
│   │   ├── keycode.py             # Enum de KeyCodes Android
│   │   └── file_manager.py        # list_files_by_path() — wrapper de ls -la
│   ├── core/
│   │   ├── constants.py           # Constantes globais (PORT)
│   │   └── logger_config.py       # Configuração do Loguru
│   ├── model/
│   │   ├── adboutput.py           # Modelo Pydantic AdbResponse
│   │   └── file_entry.py          # Modelos FileEntry e FileManagerResponse + parse_ls_output()
│   ├── routes/
│   │   ├── device.py              # Endpoints REST e WebSocket (usa DeviceService via Depends)
│   │   └── health.py              # GET /health
│   └── services/
│       └── device_service.py      # DeviceService: toda a lógica de negócio + get_device_service()
├── logs/                          # Logs rotativos gerados pelo Loguru
└── tests/
    └── test_device_api.py         # Testes unitários com mocks
```

### Injeção de Dependência

As rotas **não** gerenciam conexões diretamente. O padrão é:

```
DeviceManager (singleton em app/dependencies.py)
    └── DeviceService (instanciado por request via Depends)
            └── Rotas (recebem DeviceService via Depends(get_device_service))
```

```python
# Padrão nas rotas
@router.get("/device/{serial}/screenshot")
def screenshot(serial: str, svc: DeviceService = Depends(get_device_service)):
    return svc.screenshot(serial)
```

Os testes sobrescrevem a dependência via `app.dependency_overrides`:

```python
app.dependency_overrides[get_device_service] = lambda: DeviceService(_make_mock_manager(mock_device))
```

### Fluxo de vídeo via WebSocket

```
Cliente (navegador)
    │
    ▼  ws://localhost:8000/ws/device/{serial}/control
FastAPI WebSocket
    │
    ├── ScrcpyServer._stream_video_to_websocket()  ─►  frames JPEG para o cliente
    └── ScrcpyServer._handle_control_websocket()   ◄─  eventos JSON do cliente
            │
            └── ScrcpyTouchController  ─►  protocolo binário scrcpy ─►  dispositivo
```

---

## Requisitos

- **Python** 3.12+
- **ADB** instalado e acessível no `PATH`
- Dispositivo Android conectado via USB com **depuração USB** habilitada
- Arquivo JAR do scrcpy server em `app/binaries/scrcpy-server-v2.7.jar`

Principais dependências Python:

| Pacote | Versão |
|---|---|
| fastapi | 0.135.1 |
| uvicorn | 0.42.0 |
| uiautomator2 | 3.5.0 |
| adbutils | 2.12.0 |
| pydantic | 2.12.5 |
| pillow | 12.1.1 |
| loguru | 0.7.3 |
| mcp | ≥1.27.1 |
| av | 17.0.0 |

---

## Instalação

O projeto usa **UV** para gerenciamento de dependências.

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd fast_bridge_backend

# Instale as dependências com UV (recomendado)
uv sync

# Ou com pip tradicional
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

---

## Executando o Projeto

```bash
python main.py
```

O servidor sobe em `http://localhost:8000`.
- Swagger UI: `http://localhost:8000/docs`
- MCP (Streamable HTTP): `http://localhost:8000/mcp`

---

## Endpoints da API

### Health

#### `GET /health`

Verifica se o servidor está em execução.

**Resposta `200`**
```json
{ "status": "ok" }
```

---

### Dispositivos

#### `GET /devices`

Lista todos os dispositivos Android conectados via ADB.

**Resposta `200`**
```json
[
  {
    "serialno": "RQCTA0823SP",
    "devpath": "usb:1-2",
    "state": "device"
  }
]
```

---

### Captura e Informações

#### `GET /device/{device_serial}/screenshot`

Retorna um screenshot do dispositivo como imagem JPEG.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `device_serial` | path | Serial do dispositivo |
| `display_id` | query | ID do display (padrão: `0`) |

**Resposta `200`** — `image/jpeg`

---

#### `GET /device/{device_serial}/screen_info`

Retorna as dimensões da tela do dispositivo.

**Resposta `200`**
```json
{
  "width": 1080,
  "height": 2400
}
```

---

#### `GET /device/{device_serial}/prop/{shell_property}`

Consulta uma propriedade do sistema Android via `getprop`.

**Exemplo:** `GET /device/emulator-5554/prop/ro.product.model`

**Resposta `200`** — [`AdbResponse`](#adbresponse)
```json
{
  "device_serial": "emulator-5554",
  "stdout": "Pixel 6",
  "exit_code": 0
}
```

**Resposta `505`** — Erro de ADB.

---

#### `GET /device/{device_serial}/window_dump`

Retorna o dump da hierarquia de UI do dispositivo em XML (uiautomator2).

| Parâmetro | Tipo | Valores | Descrição |
|---|---|---|---|
| `format` | query | `xml` | Formato de saída (padrão: `xml`). Outros valores retornam `400`. |

**Resposta `200`** — `text/xml`

---

### Gerenciador de Arquivos

#### `GET /device/{device_serial}/file_manager`

Lista arquivos e diretórios em um caminho do dispositivo via `ls -la`.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `device_serial` | path | Serial do dispositivo |
| `path` | query | Caminho no dispositivo (padrão: `.`) |

**Resposta `200`** — [`FileManagerResponse`](#filemanagerresponse)
```json
{
  "path": "/sdcard",
  "entries": [
    {
      "name": "Download",
      "permissions": "drwxrwx--x",
      "is_dir": true,
      "is_symlink": false,
      "owner": "root",
      "group": "sdcard_rw",
      "size": 4096,
      "modified_at": "2024-01-15 10:30",
      "symlink_target": null
    }
  ]
}
```

---

### Entrada (Input)

#### `POST /device/{device_serial}/input/keyevent`

Envia um evento de tecla Android.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `keycode` | query | Código da tecla Android (ex.: `4` = BACK, `66` = ENTER) |
| `repeat` | query | Número de repetições com longpress (padrão: `0`) |
| `metastate` | query | Flags de meta state (padrão: `0`) |

**Resposta `200`**
```json
{ "detail": "Key event 4 sent to device emulator-5554" }
```

---

#### `PUT /device/{device_serial}/input/text`

Envia uma string de texto para o dispositivo.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `text` | query | Texto a ser digitado |

**Resposta `200`**
```json
{ "detail": "Text sent to device emulator-5554" }
```

---

#### `PUT /device/{device_serial}/input/touch`

Envia um evento de toque (tap) em coordenadas absolutas.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `x` | query | Coordenada X em pixels |
| `y` | query | Coordenada Y em pixels |

**Resposta `200`**
```json
{ "detail": "Touch event sent to device emulator-5554 at (540, 960)" }
```

---

### Shell ADB

#### `POST /device/{device_serial}`

Executa um comando shell no dispositivo via ADB. O body deve ser uma lista de strings (tokens).

**Body** `application/json`
```json
["pm", "list", "packages"]
```

**Resposta `200`** — [`AdbResponse`](#adbresponse)
```json
{
  "device_serial": "emulator-5554",
  "stdout": "package:com.example.app\n...",
  "exit_code": 0
}
```

**Resposta `505`** — Erro de ADB.

---

### WebSocket — Controle em Tempo Real

#### `WS /ws/device/{device_serial}/control`

Canal bidirecional que combina streaming de vídeo (scrcpy) com controle do dispositivo.

**Mensagens do cliente → servidor** (JSON):

| `type` | Campos adicionais | Descrição |
|---|---|---|
| `touchDown` | `xP`, `yP` (0.0–1.0) | Toque iniciado (coordenadas percentuais) |
| `touchMove` | `xP`, `yP` (0.0–1.0) | Arrastar |
| `touchUp` | `xP`, `yP` (0.0–1.0) | Toque liberado |
| `keyEvent` | `data.eventNumber` | Evento de tecla Android |
| `text` | `detail` | Envio de texto via broadcast (`am broadcast`) |
| `ping` | — | Keepalive |

> Coordenadas `xP`/`yP` são percentuais (0.0–1.0). O servidor converte para pixels absolutos usando a resolução obtida no handshake do scrcpy.

**Mensagens do servidor → cliente**:

- Frames de vídeo binários JPEG
- `{"type": "pong"}` em resposta ao `ping`

---

## Servidor MCP

O servidor MCP é montado em `/mcp` (Streamable HTTP transport) e expõe ferramentas para controle de dispositivos por LLMs (ex.: Claude).

**Configuração no Claude Desktop:**
```json
{ "url": "http://localhost:8000/mcp" }
```

### Ferramentas disponíveis

#### `list_connected_devices`

Retorna os seriais de todos os dispositivos ADB conectados.

**Retorno:** `list[str]`

---

#### `get_ui_hierarchy(serial)`

Retorna o dump XML da hierarquia de UI da tela atual do dispositivo.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `serial` | str | Serial ADB do dispositivo |

**Retorno:** `str` — XML UTF-8 da hierarquia de views.

---

#### `take_screenshot(serial)`

Captura um screenshot e retorna como string base64 (JPEG).

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `serial` | str | Serial ADB do dispositivo |

**Retorno:** `str` — JPEG codificado em base64.

---

#### `execute_adb_command(serial, command)`

Executa um comando ADB shell autorizado no dispositivo.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `serial` | str | Serial ADB do dispositivo |
| `command` | `list[str]` | Comando tokenizado, ex.: `["input", "tap", "540", "960"]` |

Comandos permitidos: `input`, `am`, `pm`, `dumpsys`, `getprop`, `settings`, `service`, `wm`, `cmd`.

Metacaracteres de shell (`;`, `|`, `&`, `$`, `` ` ``, `>`, `<`) são **rejeitados**.

**Retorno:**
```json
{ "stdout": "...", "exit_code": 0 }
```

---

## Modelos de Dados

### `AdbResponse`

```python
class AdbResponse(BaseModel):
    device_serial: str   # Serial do dispositivo
    stdout: str          # Saída do comando
    exit_code: int       # 0 = sucesso, 1 = erro
```

### `FileEntry`

```python
class FileEntry(BaseModel):
    name: str
    permissions: str         # ex.: "drwxr-xr-x"
    is_dir: bool
    is_symlink: bool
    owner: str
    group: str
    size: int
    modified_at: str         # ex.: "2024-01-15 10:30"
    symlink_target: str | None
```

### `FileManagerResponse`

```python
class FileManagerResponse(BaseModel):
    path: str
    entries: list[FileEntry]
```

---

## Estrutura do Projeto

| Módulo | Responsabilidade |
|---|---|
| `main.py` | Configuração do app FastAPI, CORS, Uvicorn e montagem do MCP em `/mcp` |
| `mcp_server.py` | Servidor MCP com as 4 ferramentas de controle de dispositivo |
| `app/dependencies.py` | `DeviceManager` singleton; provedor `get_device_manager()` |
| `app/services/device_service.py` | `DeviceService`: toda a lógica de negócio; provedor `get_device_service()` |
| `app/routes/device.py` | Endpoints REST e WebSocket; injetam `DeviceService` via `Depends` |
| `app/routes/health.py` | `GET /health` |
| `app/controller/scrcpy.py` | Gerencia o servidor scrcpy no dispositivo, streaming de vídeo e controle via WebSocket |
| `app/controller/touch_controller.py` | Serializa eventos de toque no protocolo binário do scrcpy |
| `app/controller/android_input.py` | Enums `KeyeventAction` e `MetaState` |
| `app/controller/keycode.py` | Enum `KeyCode` com todos os keycodes Android |
| `app/controller/file_manager.py` | `list_files_by_path()` — executa `ls -la` e retorna `FileManagerResponse` |
| `app/model/adboutput.py` | Schema Pydantic `AdbResponse` |
| `app/model/file_entry.py` | Schemas `FileEntry` e `FileManagerResponse` + `parse_ls_output()` |
| `app/core/constants.py` | Constantes globais |
| `app/core/logger_config.py` | Loguru configurado com rotação e compressão |

---

## Testes

Os testes usam `pytest` com `unittest.mock` para isolar dependências ADB. As dependências são injetadas via `app.dependency_overrides`.

```bash
pytest tests/
# Ou um teste específico:
pytest tests/test_device_api.py::test_send_adb_shell_success
```

Casos de teste cobertos em `tests/test_device_api.py`:

- `GET /devices` — listagem de dispositivos mockados
- `POST /device/{serial}` — execução de shell com sucesso e com erro (`505`)
- `GET /device/{serial}/prop/{property}` — consulta de propriedade

---

## Logging

Configurado via **Loguru**. Logs são emitidos para:

- **stderr** — nível `INFO`
- **`logs/app_YYYY-MM-DD.log`** — nível `INFO`, rotação a cada 5 MB, retenção de 7 dias, compressão ZIP

> **Atenção:** Use `from app.core import log` em todo código dentro de `app/`. Nunca use `print()` ou `logging.getLogger()`.

---

## Frontend

O frontend da aplicação está disponível em [fast-bridge-nine.vercel.app](https://fast-bridge-nine.vercel.app) e se comunica com este backend via HTTP e WebSocket.
