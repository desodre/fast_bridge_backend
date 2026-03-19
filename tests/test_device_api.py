import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from main import app

client = TestClient(app)


@patch('adbutils.adb.device_list')
def test_adb_device_list(mock_adb_list):
    mock_device1 = MagicMock(serial='SERIAL1')
    mock_device2 = MagicMock(serial='SERIAL2')
    mock_adb_list.return_value = [mock_device1, mock_device2]

    response = client.get('/devices')

    assert response.status_code == 200
    assert response.json() == ['SERIAL1', 'SERIAL2']
