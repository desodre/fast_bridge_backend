from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app
from app.dependencies import get_device_manager, DeviceManager
from app.services.device_service import DeviceService, get_device_service
from app.model.file_entry import FileManagerResponse, FileEntry


def _make_service(mock_device: MagicMock) -> DeviceService:
    manager = MagicMock(spec=DeviceManager)
    manager.get_device.return_value = mock_device
    return DeviceService(manager)


client = TestClient(app)


@patch('adbutils.adb.device_list')
def test_adb_device_list(mock_adb_list):
    mock_device1 = MagicMock(info={'serial': 'SERIAL1'})
    mock_device2 = MagicMock(info={'serial': 'SERIAL2'})
    mock_adb_list.return_value = [mock_device1, mock_device2]

    response = client.get('/devices')

    assert response.status_code == 200
    assert response.json() == [{'serial': 'SERIAL1'}, {'serial': 'SERIAL2'}]


def test_send_adb_shell_success():
    mock_device = MagicMock()
    mock_device.shell.return_value = MagicMock(output='ok', exit_code=0)

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.post('/device/SERIAL1', json=['echo', 'ok'])
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    assert response.json() == {'device_serial': 'SERIAL1', 'stdout': 'ok', 'exit_code': 0}
    mock_device.shell.assert_called_once_with(['echo', 'ok'])


def test_send_adb_shell_error_returns_505():
    mock_device = MagicMock()
    mock_device.shell.side_effect = RuntimeError('shell failed')

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.post('/device/SERIAL1', json=['bad', 'cmd'])
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 505
    assert 'ADB erro shell failed' in response.json()['detail']


def test_get_property_success():
    mock_device = MagicMock()
    mock_device.shell.return_value = MagicMock(output='Pixel', exit_code=0)

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.get('/device/SERIAL1/prop/ro.product.model')
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    assert response.json() == {'device_serial': 'SERIAL1', 'stdout': 'Pixel', 'exit_code': 0}
    mock_device.shell.assert_called_once_with(['getprop', 'ro.product.model'])


def test_get_property_error_returns_505():
    mock_device = MagicMock()
    mock_device.shell.side_effect = RuntimeError('adb unavailable')

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.get('/device/SERIAL1/prop/ro.product.model')
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 505
    assert 'ADB erro adb unavailable' in response.json()['detail']


def test_window_dump_xml_response():
    mock_device = MagicMock()
    mock_device.dump_hierarchy.return_value = '<hierarchy />'

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.get('/device/SERIAL1/window_dump?format=xml')
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    assert response.text == '<hierarchy />'
    assert response.headers['content-type'].startswith('text/xml')


def test_send_touch_calls_expected_shell_command():
    mock_device = MagicMock()

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.put('/device/SERIAL1/input/touch', params={'x': 120, 'y': 240})
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    assert response.json()['detail'] == 'Touch event sent to device SERIAL1 at (120, 240)'
    mock_device.shell.assert_called_once_with(['input', 'touchscreen', 'tap', '120', '240'])


def test_get_device_screen_info_maps_width_and_height():
    mock_device = MagicMock()
    mock_device.window_size.return_value = (1080, 1920)

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.get('/device/SERIAL1/screen_info')
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    assert response.json() == {'width': 1080, 'height': 1920}


def test_file_manager_returns_parsed_entries():
    mock_device = MagicMock()
    mock_device.shell.return_value = MagicMock(
        output=(
            'total 8\n'
            '-rw-r--r-- 1 root root 1234 2024-01-15 10:30 file.txt\n'
            'drwxr-xr-x 2 root root 4096 2024-01-15 10:31 subdir\n'
            'lrwxrwxrwx 1 root root   11 2024-01-15 10:32 link -> /target\n'
        ),
        exit_code=0,
    )

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.get('/device/SERIAL1/file_manager', params={'path': '/sdcard'})
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body['path'] == '/sdcard'
    entries = body['entries']
    assert len(entries) == 3

    file_entry = entries[0]
    assert file_entry['name'] == 'file.txt'
    assert file_entry['is_dir'] is False
    assert file_entry['is_symlink'] is False
    assert file_entry['size'] == 1234

    dir_entry = entries[1]
    assert dir_entry['name'] == 'subdir'
    assert dir_entry['is_dir'] is True

    link_entry = entries[2]
    assert link_entry['is_symlink'] is True
    assert link_entry['symlink_target'] == '/target'


def test_file_manager_default_path():
    mock_device = MagicMock()
    mock_device.shell.return_value = MagicMock(output='', exit_code=0)

    app.dependency_overrides[get_device_service] = lambda: _make_service(mock_device)
    try:
        response = client.get('/device/SERIAL1/file_manager')
    finally:
        app.dependency_overrides.pop(get_device_service, None)

    assert response.status_code == 200
    assert response.json()['path'] == '.'
    mock_device.shell.assert_called_once_with(['ls', '-la', '.'])
