from unittest.mock import patch

import pytest

from vendor import road


TARGET_EMAIL = "gaoxiaowei2117@gmail.com"


def _config(tmp_path):
    return {
        "emailReplace": {"enable": True},
        "data_directory": str(tmp_path),
        "icbc": {
            "licenceNumber": "1234567",
            "originalEmail": "original@example.com",
        },
    }


def _driver(email):
    return {
        "email": email,
        "drvrId": "driver-1",
        "licenseNumber": "1234567",
    }


def test_email_sync_skips_when_icbc_email_is_target(tmp_path):
    config = _config(tmp_path)

    with patch.object(road, "update_contact_email") as update:
        road.ensure_email_synced(config, "token", _driver(TARGET_EMAIL))

    update.assert_not_called()


def test_email_sync_replaces_non_target_icbc_email(tmp_path):
    config = _config(tmp_path)
    weblogin_data = _driver("original@example.com")

    with patch.object(road, "update_contact_email", return_value=True) as update:
        road.ensure_email_synced(config, "token", weblogin_data)

    update.assert_called_once_with("token", weblogin_data, TARGET_EMAIL)
    assert weblogin_data["email"] == TARGET_EMAIL


def test_email_sync_accepts_icbc_numeric_licence_without_leading_zero(tmp_path):
    config = _config(tmp_path)
    config["icbc"]["licenceNumber"] = "01234567"
    weblogin_data = _driver("original@example.com")
    weblogin_data["licenseNumber"] = 1234567

    with patch.object(road, "update_contact_email", return_value=True) as update:
        road.ensure_email_synced(config, "token", weblogin_data)

    update.assert_called_once_with("token", weblogin_data, TARGET_EMAIL)


def test_email_sync_rejects_unexpected_current_email(tmp_path):
    config = _config(tmp_path)
    weblogin_data = _driver("another-driver@example.com")

    with patch.object(road, "update_contact_email") as update, \
         pytest.raises(road.EmailSafetyError, match="当前邮箱"):
        road.ensure_email_synced(config, "token", weblogin_data)

    update.assert_not_called()


def test_restore_uses_configured_original_email(tmp_path):
    config = _config(tmp_path)
    weblogin_data = _driver(TARGET_EMAIL)

    with patch.object(road, "update_contact_email", return_value=True) as update:
        restored = road.restore_original_email(config, "token", weblogin_data)

    assert restored is True
    update.assert_called_once_with("token", weblogin_data, "original@example.com")
    assert weblogin_data["email"] == "original@example.com"


def test_restore_refuses_mismatched_driver(tmp_path):
    config = _config(tmp_path)
    weblogin_data = _driver(TARGET_EMAIL)
    weblogin_data["licenseNumber"] = "7654321"

    with patch.object(road, "update_contact_email") as update:
        restored = road.restore_original_email(config, "token", weblogin_data)

    assert restored is False
    update.assert_not_called()
