"""
Fast Bridge MCP Server
======================
Exposes Android device control tools to LLMs (e.g. Claude) via the
Model Context Protocol using stdio transport.

Logging goes to stderr so that stdout remains clean for the MCP protocol.
Run with:
    python mcp_server.py
or via Claude Desktop (see claude_desktop_config.json instructions).
"""

import base64
import sys

import adbutils
from mcp.server.fastmcp import FastMCP

from app.dependencies import DeviceManager
from app.services.device_service import DeviceService

# ---------------------------------------------------------------------------
# Initialise FastMCP and a single shared DeviceManager (mirrors the FastAPI
# singleton pattern in app/dependencies.py).
# ---------------------------------------------------------------------------

mcp = FastMCP("fast-bridge")

_manager = DeviceManager()


def _get_service(serial: str) -> DeviceService:
    """Return a DeviceService bound to the shared manager."""
    return DeviceService(_manager)


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {"input", "am", "pm", "dumpsys", "getprop", "settings", "service", "wm", "cmd"}
)

_SHELL_INJECTION_CHARS: frozenset[str] = frozenset(
    {";", "|", "&", "`", "$", ">", "<", "\n", "\r"}
)


def _validate_command(command: list[str]) -> None:
    """Raise ValueError if *command* is empty, disallowed, or contains shell
    injection characters."""
    if not command:
        raise ValueError("command list cannot be empty")

    top = command[0].lower()
    if top not in _ALLOWED_COMMANDS:
        raise ValueError(
            f"Command '{top}' is not permitted. "
            f"Allowed commands: {sorted(_ALLOWED_COMMANDS)}"
        )

    for part in command:
        bad = _SHELL_INJECTION_CHARS.intersection(part)
        if bad:
            raise ValueError(
                f"Illegal character(s) {bad!r} detected in argument: {part!r}"
            )


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_connected_devices() -> list[str]:
    """Return the serial numbers of all Android devices currently connected via ADB."""
    devices = adbutils.adb.device_list()
    serials = [d.serial for d in devices]
    print(f"[fast_bridge] list_connected_devices → {serials}", file=sys.stderr)
    return serials


@mcp.tool()
def get_ui_hierarchy(serial: str) -> str:
    """Dump the current UI XML hierarchy of the device screen.

    Args:
        serial: ADB serial of the target device (e.g. "emulator-5554").

    Returns:
        UTF-8 XML string representing the view hierarchy.
    """
    try:
        svc = _get_service(serial)
        xml = svc.get_window_dump(serial)
        print(
            f"[fast_bridge] get_ui_hierarchy({serial}) → {len(xml)} chars",
            file=sys.stderr,
        )
        return xml
    except Exception as exc:
        print(
            f"[fast_bridge] get_ui_hierarchy({serial}) ERROR: {exc}",
            file=sys.stderr,
        )
        raise


@mcp.tool()
def take_screenshot(serial: str) -> str:
    """Capture a screenshot from the device and return it as a base64-encoded JPEG.

    Args:
        serial: ADB serial of the target device.

    Returns:
        Base64-encoded JPEG string that can be decoded and displayed.
    """
    try:
        svc = _get_service(serial)
        jpeg_bytes = svc.screenshot(serial)
        encoded = base64.b64encode(jpeg_bytes).decode("ascii")
        print(
            f"[fast_bridge] take_screenshot({serial}) → {len(jpeg_bytes)} bytes",
            file=sys.stderr,
        )
        return encoded
    except Exception as exc:
        print(
            f"[fast_bridge] take_screenshot({serial}) ERROR: {exc}",
            file=sys.stderr,
        )
        raise


@mcp.tool()
def execute_adb_command(serial: str, command: list[str]) -> dict[str, object]:
    """Execute a whitelisted ADB shell command on the device.

    Allowed top-level commands: input, am, pm, dumpsys, getprop, settings,
    service, wm, cmd.

    Args:
        serial:  ADB serial of the target device.
        command: Tokenised shell command, e.g. ["input", "tap", "540", "960"].

    Returns:
        A dict with keys ``stdout`` (str) and ``exit_code`` (int).

    Raises:
        ValueError: If the command is disallowed or contains injection characters.
    """
    _validate_command(command)

    try:
        svc = _get_service(serial)
        result = svc.run_shell(serial, command)
        print(
            f"[fast_bridge] execute_adb_command({serial}, {command}) "
            f"exit={result.exit_code}",
            file=sys.stderr,
        )
        return {"stdout": result.stdout, "exit_code": result.exit_code}
    except Exception as exc:
        print(
            f"[fast_bridge] execute_adb_command({serial}, {command}) ERROR: {exc}",
            file=sys.stderr,
        )
        raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("[fast_bridge] Starting Fast Bridge MCP Server via stdio…", file=sys.stderr)
    mcp.run(transport="stdio")
