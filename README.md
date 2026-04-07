# fast_bridge_backend

Backend da aplicação **Fast Bridge** — uma API REST e WebSocket para controle remoto de dispositivos Android via ADB e uiautomator2, com streaming de vídeo em tempo real via scrcpy.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Executando o Projeto](#executando-o-projeto)
- [Endpoints da API](#endpoints-da-api)
  - [Dispositivos](#dispositivos)
  - [Captura e Informações](#captura-e-informações)
  - [Entrada (Input)](#entrada-input)
  - [Shell ADB](#shell-adb)
  - [WebSocket — Controle em Tempo Real](#websocket--controle-em-tempo-real)
- [Modelos de Dados](#modelos-de-dados)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Logging](#logging)
- [Frontend](#frontend)

---

## Visão Geral

O **Fast Bridge Backend** expõe dispositivos Android conectados via USB (ADB) como recursos HTTP e WebSocket. Com ele é possível:

- Listar dispositivos conectados
- Tirar screenshots
- Consultar propriedades do sistema e informações de tela
- Executar comandos shell arbitrários via ADB
- Enviar eventos de toque, teclas e texto
- Fazer streaming de vídeo e controlar o dispositivo em tempo real via WebSocket (protocolo scrcpy)

---

## Arquitetura

```
fast_bridge_backend/
├── main.py                        # Ponto de entrada — FastAPI + Uvicorn
├── requirements.txt
├── app/
│   ├── binaries/                  # scrcpy-server-v*.jar
│   ├── controller/
│   │   ├── scrcpy.py              # ScrcpyServer: streaming de vídeo + controle WebSocket
│   │   ├── touch_controller.py    # Protocolo binário de toque para scrcpy
│   │   ├── android_input.py       # Constantes de input Android (KeyeventAction, MetaState)
│   │   └── keycode.py             # Enum de KeyCodes Android
│   ├── core/
│   │   ├── constants.py           # Constantes globais (PORT)
│   │   └── logger_config.py       # Configuração do Loguru
│   ├── model/
│   │   └── adboutput.py           # Modelo Pydantic AdbResponse
│   └── routes/
│       └── device.py              # Todos os endpoints REST e WebSocket
├── logs/                          # Logs rotativos gerados pelo Loguru
└── tests/
    └── test_device_api.py         # Testes unitários com mocks
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

- **Python** 3.10+
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

---

## Instalação

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd fast_bridge_backend

# Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\Scripts\activate    # Windows

# Instale as dependências
pip install -r requirements.txt
```

---

## Executando o Projeto

```bash
python main.py
```

O servidor sobe em `http://localhost:8000`. O Swagger UI fica disponível em `http://localhost:8000/docs`.

---

## Endpoints da API

### Dispositivos

#### `GET /devices`

Lista todos os dispositivos Android conectados via ADB.

**Resposta `200`**
```json
[
  {
    "serial": "emulator-5554",
    "state": "device",
    ...
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

**Resposta `200`**
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

Retorna o dump da hierarquia de UI do dispositivo.

| Parâmetro | Tipo | Valores | Descrição |
|---|---|---|---|
| `format` | query | `xml` | Formato de saída (padrão: `xml`) |

**Resposta `200`** — `text/xml`

---

### Entrada (Input)

#### `POST /device/{device_serial}/input/touch`

Envia um evento de toque (tap) em coordenadas absolutas.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `x` | query | Coordenada X em pixels |
| `y` | query | Coordenada Y em pixels |

---

#### `POST /device/{device_serial}/input/keyevent`

Envia um evento de tecla Android.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `keycode` | query | Código da tecla Android (ex.: `4` = BACK) |
| `repeat` | query | Número de repetições (padrão: `0`) |
| `metastate` | query | Flags de meta state (padrão: `0`) |

---

#### `POST /device/{device_serial}/input/text`

Envia uma string de texto para o dispositivo.

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `text` | query | Texto a ser digitado |

---

### Shell ADB

#### `POST /device/{device_serial}`

Executa um comando shell arbitrário no dispositivo via ADB.

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
| `text` | `detail` | Envio de texto via broadcast |
| `ping` | — | Keepalive |

**Mensagens do servidor → cliente**:

- Frames de vídeo binários (protocolo scrcpy)
- `{"type": "pong"}` em resposta ao `ping`

---

## Modelos de Dados

### `AdbResponse`

```python
class AdbResponse(BaseModel):
    device_serial: str   # Serial do dispositivo
    stdout: str          # Saída do comando
    exit_code: int       # 0 = sucesso, 1 = erro
```

---

## Estrutura do Projeto

| Módulo | Responsabilidade |
|---|---|
| `main.py` | Configuração do app FastAPI, CORS e inicialização do Uvicorn |
| `app/routes/device.py` | Definição de todos os endpoints REST e WebSocket; cache de conexões de dispositivos |
| `app/controller/scrcpy.py` | Gerencia o servidor scrcpy no dispositivo, streaming de vídeo e controle via WebSocket |
| `app/controller/touch_controller.py` | Serializa eventos de toque no protocolo binário do scrcpy |
| `app/controller/android_input.py` | Enums `KeyeventAction` e `MetaState` |
| `app/controller/keycode.py` | Enum `KeyCode` com todos os keycodes Android |
| `app/model/adboutput.py` | Schema Pydantic `AdbResponse` |
| `app/core/constants.py` | Constantes globais |
| `app/core/logger_config.py` | Loguru configurado com rotação e compressão |

---

## Testes

Os testes usam `pytest` com `unittest.mock` para isolar dependências ADB.

```bash
pytest tests/
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

---

## Frontend

O frontend da aplicação está disponível em [fast-bridge-nine.vercel.app](https://fast-bridge-nine.vercel.app) e se comunica com este backend via HTTP e WebSocket.
