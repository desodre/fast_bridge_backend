from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app
from app.routes import device as device_routes

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
    mock_output = MagicMock(output='ok', exit_code=0)
    mock_device = MagicMock()
    mock_device.shell.return_value = mock_output

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.post('/device/SERIAL1', json=['echo', 'ok'])

    assert response.status_code == 200
    assert response.json() == {
        'device_serial': 'SERIAL1',
        'stdout': 'ok',
        'exit_code': 0,
    }
    mock_device.shell.assert_called_once_with(['echo', 'ok'])


def test_send_adb_shell_error_returns_505():
    mock_device = MagicMock()
    mock_device.shell.side_effect = RuntimeError('shell failed')

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.post('/device/SERIAL1', json=['bad', 'cmd'])

    assert response.status_code == 505
    assert 'ADB erro shell failed' in response.json()['detail']


def test_get_property_success():
    mock_output = MagicMock(output='Pixel', exit_code=0)
    mock_device = MagicMock()
    mock_device.shell.return_value = mock_output

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.get('/device/SERIAL1/prop/ro.product.model')

    assert response.status_code == 200
    assert response.json() == {
        'device_serial': 'SERIAL1',
        'stdout': 'Pixel',
        'exit_code': 0,
    }
    mock_device.shell.assert_called_once_with(['getprop', 'ro.product.model'])


def test_get_property_error_returns_505():
    mock_device = MagicMock()
    mock_device.shell.side_effect = RuntimeError('adb unavailable')

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.get('/device/SERIAL1/prop/ro.product.model')

    assert response.status_code == 505
    assert 'ADB erro adb unavailable' in response.json()['detail']


def test_window_dump_xml_response():
    mock_device = MagicMock()
    mock_device.dump_hierarchy.return_value = '<hierarchy />'

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.get('/device/SERIAL1/window_dump?format=xml')

    assert response.status_code == 200
    assert response.text == '<hierarchy />'
    assert response.headers['content-type'].startswith('text/xml')


def test_send_touch_calls_expected_shell_command():
    mock_device = MagicMock()

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.post('/device/SERIAL1/input/touch', params={'x': 120, 'y': 240})

    assert response.status_code == 200
    assert response.json()['detail'] == 'Touch event sent to device SERIAL1 at (120, 240)'
    mock_device.shell.assert_called_once_with('input touchscreen tap 120 240')


@patch('uiautomator2.connect')
def test_get_cached_device_reuses_cached_instance(mock_connect):
    device_routes._connected_devices.clear()
    first_device = MagicMock()
    mock_connect.return_value = first_device

    first_call = device_routes.get_cached_device('SERIAL1')
    second_call = device_routes.get_cached_device('SERIAL1')

    assert first_call is second_call
    mock_connect.assert_called_once_with('SERIAL1')


def test_get_device_screen_info_maps_width_and_height():
    mock_device = MagicMock()
    mock_device.window_size.return_value = (1080, 1920)

    with patch('app.routes.device.get_cached_device', return_value=mock_device):
        response = client.get('/device/SERIAL1/screen_info')

    assert response.status_code == 200
    assert response.json() == {'width': 1080, 'height': 1920}
