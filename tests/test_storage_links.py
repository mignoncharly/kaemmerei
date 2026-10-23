"""Actual Windows junction rejection, separate from symbolic-link privileges."""
import os
from pathlib import Path
import subprocess
import pytest
from app.config import Settings
from tests.support import scratch_directory


@pytest.mark.skipif(os.name!='nt',reason='Windows native junction only')
def test_actual_windows_junction_storage_and_parent_are_rejected():
    with scratch_directory('ohvr-junction-') as directory:
        root=Path(directory);target=root/'target';target.mkdir()
        sentinel=target/'synthetic.txt';sentinel.write_bytes(b'Synthetic junction fixture')
        link=root/'junction'
        try:
            result=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(link),str(target)],
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
            if result.returncode or not link.is_junction():
                if os.getenv('REQUIRE_NATIVE_LINKS')=='1':pytest.fail('Required Windows junction creation unavailable')
                pytest.skip('Windows junction creation unavailable under this test identity')
            assert link.resolve()==target.resolve()
            for path in (link,link/'not-created'):
                with pytest.raises(ValueError,match='Linked storage'):
                    Settings(document_storage_dir=path).validate()
            assert sentinel.read_bytes()==b'Synthetic junction fixture'
        finally:
            # Remove only this junction entry, never its target or an unrelated path.
            if link.is_junction():os.rmdir(link)
        assert target.is_dir() and sentinel.exists()


def test_required_symbolic_link_check_cannot_skip_on_missing_privilege(monkeypatch):
    from tests.test_phase5 import test_actual_linked_storage_is_rejected
    monkeypatch.setenv('REQUIRE_NATIVE_LINKS','1')
    def unavailable(*args,**kwargs):raise OSError('Synthetic unavailable privilege')
    monkeypatch.setattr(Path,'symlink_to',unavailable)
    with scratch_directory('ohvr-required-link-') as directory:
        with pytest.raises(pytest.fail.Exception,match='release gate cannot skip'):
            test_actual_linked_storage_is_rejected(Path(directory))
