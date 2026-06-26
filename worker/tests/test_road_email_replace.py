import json
from unittest.mock import patch

from vendor import road


TARGET_EMAIL = "gaoxiaowei2117@gmail.com"


def test_email_sync_skips_when_icbc_email_is_target(tmp_path):
    config = {
        "emailReplace": {"enable": True},
        "data_directory": str(tmp_path),
    }

    with patch.object(road, "update_contact_email") as update:
        road.ensure_email_synced(config, "token", {"email": TARGET_EMAIL})

    update.assert_not_called()
    assert not (tmp_path / "icbc_email_backup.json").exists()


def test_email_sync_replaces_non_target_icbc_email(tmp_path):
    config = {
        "emailReplace": {"enable": True},
        "data_directory": str(tmp_path),
    }
    weblogin_data = {
        "email": "original@example.com",
        "drvrId": "driver-1",
        "licenseNumber": "1234567",
    }

    with patch.object(road, "update_contact_email", return_value=True) as update:
        road.ensure_email_synced(config, "token", weblogin_data)

    update.assert_called_once_with("token", weblogin_data, TARGET_EMAIL)
    assert weblogin_data["email"] == TARGET_EMAIL
    backup = json.loads((tmp_path / "icbc_email_backup.json").read_text())
    assert backup["original_email"] == "original@example.com"
