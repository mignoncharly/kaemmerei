"""Fail closed when database ownership, OID, marker or generated name changes."""
from unittest.mock import Mock

import pytest

from tests.support import drop_disposable_database, require_database_identity


@pytest.mark.parametrize('actual', [None, (43, 'ohvr_verify', 'marker'),
                                   (42, 'other_owner', 'marker'), (42, 'ohvr_verify', 'other_marker')])
def test_cleanup_rejects_replaced_or_unmarked_database(actual):
    control = Mock()
    control.execute.return_value.fetchone.return_value = actual
    with pytest.raises(RuntimeError, match='identity changed'):
        require_database_identity(control, 'ohvr_test_' + 'a' * 32, (42, 'ohvr_verify', 'marker'))
    assert all('DROP' not in call.args[0] for call in control.execute.call_args_list)


def test_cleanup_rejects_default_database_before_querying():
    control = Mock()
    with pytest.raises(RuntimeError, match='identity changed'):
        require_database_identity(control, 'postgres', (42, 'ohvr_verify', 'marker'))
    control.execute.assert_not_called()


def test_cleanup_never_forces_termination_of_other_connections():
    control = Mock()
    expected = (42, 'ohvr_verify', 'marker')
    control.execute.return_value.fetchone.return_value = expected
    drop_disposable_database(control, 'ohvr_test_' + 'a' * 32, expected)
    statement = str(control.execute.call_args.args[0])
    assert 'DROP DATABASE' in statement
    assert 'FORCE' not in statement and 'pg_terminate_backend' not in statement
