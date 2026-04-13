import uiautomator2 as u2
from app.model.file_entry import FileManagerResponse, parse_ls_output


def list_files_by_path(device: u2.Device, path: str | None = None) -> FileManagerResponse:
    resolved_path = path or '.'
    output = device.shell(['ls', '-la', resolved_path])
    return parse_ls_output(output.output, resolved_path)
