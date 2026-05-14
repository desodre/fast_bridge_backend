import base64

import adbutils

from app.core import log
from app.dependencies import get_device_manager
from app.interfaces.mcp.server import mcp
from app.services.device_service import DeviceService

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_service() -> DeviceService:
    """Retorna um DeviceService vinculado ao singleton DeviceManager."""
    return DeviceService(get_device_manager())


# ---------------------------------------------------------------------------
# Segurança — whitelist e detecção de injeção de shell
# ---------------------------------------------------------------------------

_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {"input", "am", "pm", "dumpsys", "getprop", "settings", "service", "wm", "cmd"}
)

_SHELL_INJECTION_CHARS: frozenset[str] = frozenset(
    {";", "|", "&", "`", "$", ">", "<", "\n", "\r"}
)


def _validate_command(command: list[str]) -> None:
    """Lança ValueError se o comando for vazio, não autorizado ou contiver
    metacaracteres de shell."""
    if not command:
        raise ValueError("A lista de comandos não pode ser vazia.")

    top = command[0].lower()
    if top not in _ALLOWED_COMMANDS:
        raise ValueError(
            f"Comando '{top}' não é permitido. "
            f"Comandos permitidos: {sorted(_ALLOWED_COMMANDS)}"
        )

    for part in command:
        bad = _SHELL_INJECTION_CHARS.intersection(part)
        if bad:
            raise ValueError(
                f"Caractere(s) ilegal(is) {bad!r} detectado(s) no argumento: {part!r}"
            )


# ---------------------------------------------------------------------------
# Ferramentas MCP
# ---------------------------------------------------------------------------

@mcp.tool()
def list_connected_devices() -> list[str]:
    """Retorna os seriais de todos os dispositivos Android conectados via ADB."""
    devices = adbutils.adb.device_list()
    serials = [d.serial for d in devices]
    log.info(f"[MCP] list_connected_devices → {serials}")
    return serials


@mcp.tool()
def get_ui_hierarchy(serial: str) -> str:
    """Retorna o dump XML da hierarquia de UI da tela atual do dispositivo.

    Args:
        serial: Serial ADB do dispositivo alvo (ex.: "emulator-5554").

    Returns:
        String XML UTF-8 representando a hierarquia de views.
    """
    try:
        svc = _get_service()
        xml = svc.get_window_dump(serial)
        log.info(f"[MCP] get_ui_hierarchy({serial}) → {len(xml)} chars")
        return xml
    except Exception as exc:
        log.error(f"[MCP] get_ui_hierarchy({serial}) ERRO: {exc}")
        raise


@mcp.tool()
def take_screenshot(serial: str) -> str:
    """Captura um screenshot do dispositivo e retorna como JPEG codificado em base64.

    Args:
        serial: Serial ADB do dispositivo alvo.

    Returns:
        String base64 do JPEG capturado.
    """
    try:
        svc = _get_service()
        jpeg_bytes = svc.screenshot(serial)
        encoded = base64.b64encode(jpeg_bytes).decode("ascii")
        log.info(f"[MCP] take_screenshot({serial}) → {len(jpeg_bytes)} bytes")
        return encoded
    except Exception as exc:
        log.error(f"[MCP] take_screenshot({serial}) ERRO: {exc}")
        raise


@mcp.tool()
def execute_adb_command(serial: str, command: list[str]) -> dict[str, object]:
    """Executa um comando ADB shell autorizado no dispositivo.

    Comandos permitidos: input, am, pm, dumpsys, getprop, settings, service, wm, cmd.
    Metacaracteres de shell são rejeitados por segurança.

    Args:
        serial:  Serial ADB do dispositivo alvo.
        command: Comando tokenizado, ex.: ["input", "tap", "540", "960"].

    Returns:
        Dicionário com ``stdout`` (str) e ``exit_code`` (int).

    Raises:
        ValueError: Se o comando não for permitido ou contiver injeção de shell.
    """
    _validate_command(command)

    try:
        svc = _get_service()
        result = svc.run_shell(serial, command)
        log.info(f"[MCP] execute_adb_command({serial}, {command}) exit={result.exit_code}")
        return {"stdout": result.stdout, "exit_code": result.exit_code}
    except Exception as exc:
        log.error(f"[MCP] execute_adb_command({serial}, {command}) ERRO: {exc}")
        raise
