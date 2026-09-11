from api.auth import _roles_for_username
from settings.auth import AuthSettings


def test_temporary_accounts_keep_distinct_roles():
    settings = AuthSettings()

    assert _roles_for_username(settings.local_username, settings) == ["admin"]
    assert _roles_for_username(settings.viewer_username, settings) == ["viewer"]


def test_unknown_account_has_no_roles():
    assert _roles_for_username("unknown", AuthSettings()) == []
