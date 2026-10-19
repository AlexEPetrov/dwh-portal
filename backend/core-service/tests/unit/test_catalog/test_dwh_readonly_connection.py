from unittest.mock import MagicMock, patch

import pytest

from domains.catalog.providers.connection import connect_dwh_readonly
from settings.portal import DwhCollectorSettings


def test_connect_dwh_readonly_sets_session_read_only_option():
    settings = DwhCollectorSettings(
        psg_host="db.example",
        psg_port=5432,
        psg_user="portal",
        psg_pass="secret",
        psg_db="dwh",
    )
    fake = MagicMock()
    with patch("psycopg2.connect", return_value=fake) as connect:
        conn = connect_dwh_readonly(settings)

    assert conn is fake
    connect.assert_called_once_with(
        host="db.example",
        port=5432,
        user="portal",
        password="secret",
        dbname="dwh",
        options="-c default_transaction_read_only=on",
    )


def test_connect_dwh_readonly_requires_host_and_db():
    with pytest.raises(RuntimeError, match="not configured"):
        connect_dwh_readonly(DwhCollectorSettings(psg_host=None, psg_db="dwh"))
    with pytest.raises(RuntimeError, match="not configured"):
        connect_dwh_readonly(DwhCollectorSettings(psg_host="localhost", psg_db=None))
