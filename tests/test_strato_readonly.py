"""Synthetic-only SSH boundary tests; never connect to hosting."""
import json
import base64
import hashlib
import hmac
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.support import scratch_directory

from scripts.assess_strato_readonly import (
    AssessmentError, assess, fingerprint, load_access, policy_for, project_value,
    load_host_key_evidence,
    known_host_pins,
)


SENTINEL = "SYNTHETIC_PRIVATE_VALUE_MUST_NOT_ESCAPE"


@pytest.fixture
def tmp_path():
    # Reuse workspace-inherited scratch storage; never alter Windows ACLs.
    with scratch_directory("strato-synthetic-") as directory:
        yield Path(directory)


def access_file(tmp_path, **overrides):
    path = tmp_path / "access.json"
    path.write_text(json.dumps(dict(host="synthetic.invalid", username="synthetic", password=SENTINEL, **overrides)), encoding="utf-8")
    return path


def trust_file(tmp_path, **changes):
    data = {"expected_sha256": "SHA256:" + "A"*43, "source_kind": "trusted_console",
            "source_reference": "synthetic console receipt", "verified_at": "2026-01-01T00:00:00+00:00", "endpoint_confirmed": True}
    data.update(changes)
    path = tmp_path / "public-host-key-evidence.json"
    path.write_text(json.dumps(data))
    return path


def test_invalid_config_does_not_connect_or_disclose_contents(tmp_path):
    path = tmp_path / "access.json"
    path.write_text(SENTINEL)
    class Forbidden:
        def SSHClient(self):
            pytest.fail("No network client before successful validation")
    result = assess(path, Forbidden())
    assert result["error_code"] == "CREDENTIAL_FILE_INVALID_JSON"
    assert result["failing_stage"] == "credential_validation"
    assert SENTINEL not in json.dumps(result)
    assert path.read_text() == SENTINEL


@pytest.mark.parametrize("change", [
    {"host": "ssh://user@synthetic.invalid/path"}, {"host": "bad; command"},
    {"port": True}, {"port": 0}, {"host_key_sha256": "untrusted"},
    {"extra_command": "echo no"},
])
def test_schema_rejects_endpoint_confusion_and_commands(tmp_path, change):
    data = {"host": "synthetic.invalid", "username": "synthetic", "password": SENTINEL}
    data.update(change)
    path = tmp_path / "access.json"
    path.write_text(json.dumps(data))
    with pytest.raises(AssessmentError) as error:
        load_access(path)
    assert error.value.code == "CREDENTIAL_SCHEMA_INVALID"


def test_key_trust_never_writes_or_accepts_unknown_key():
    key = SimpleNamespace(asbytes=lambda: b"synthetic public host key")
    module = SimpleNamespace(MissingHostKeyPolicy=object)
    client = object()  # No host-key writer API available.
    with pytest.raises(AssessmentError):
        policy_for(module, None).missing_host_key(client, "synthetic.invalid", key)
    with pytest.raises(AssessmentError):
        policy_for(module, "SHA256:" + "A"*43).missing_host_key(client, "synthetic.invalid", key)
    policy_for(module, fingerprint(key)).missing_host_key(client, "synthetic.invalid", key)


@pytest.mark.parametrize("label,raw", [
    ("nginx", "nginx/1.28.0 " + SENTINEL),
    ("postgres_client", "psql (PostgreSQL) 18.6 " + SENTINEL),
    ("kernel_release", "6.8.0-" + SENTINEL),
    ("os_family", SENTINEL),
    ("uid", SENTINEL),
])
def test_remote_output_is_projected_never_copied(label, raw):
    result = project_value(label, 0, raw)
    assert SENTINEL not in json.dumps(result)
    assert SENTINEL not in json.dumps(project_value(label, 1, raw))


def test_sftp_only_host_is_partial_not_a_windows_capability_pass(tmp_path):
    path = access_file(tmp_path)
    class Client:
        def load_host_keys(self, path): pass
        def set_missing_host_key_policy(self, policy): pass
        def connect(self, **kwargs):
            assert kwargs["password"] == SENTINEL
            assert kwargs["allow_agent"] is False
            assert kwargs["look_for_keys"] is False
        def open_sftp(self):
            return SimpleNamespace(close=lambda: None)
        def exec_command(self, *args, **kwargs):
            raise RuntimeError(SENTINEL)
        def close(self): pass
    result = assess(path, SimpleNamespace(SSHClient=Client, MissingHostKeyPolicy=object), trust_file(tmp_path))
    assert result["connection_authenticated"] is True
    assert result["sftp_supported"] is True
    assert result["status"] == "PARTIAL"
    assert result["error_code"] == "SHELL_EXECUTION_UNAVAILABLE"
    assert result["isolated_windows_pilot_suitability"] == "UNVERIFIED"
    assert result["remote_changes_performed"] is False
    assert SENTINEL not in json.dumps(result)


def test_authentication_failure_does_not_disclose_secret_or_try_shell(tmp_path):
    path = access_file(tmp_path)
    class AuthenticationException(Exception): pass
    class Client:
        def load_host_keys(self, path): pass
        def set_missing_host_key_policy(self, policy): pass
        def connect(self, **kwargs): raise AuthenticationException(SENTINEL)
        def close(self): pass
    result = assess(path, SimpleNamespace(SSHClient=Client, MissingHostKeyPolicy=object), trust_file(tmp_path))
    assert result["error_code"] == "AUTHENTICATION_REJECTED"
    assert result["failing_stage"] == "ssh_authentication"
    assert result["connection_authenticated"] is False
    assert SENTINEL not in json.dumps(result)


@pytest.mark.parametrize("same_destination", [True, False])
def test_cli_never_overwrites_credentials_or_existing_report(tmp_path, monkeypatch, capsys, same_destination):
    from scripts.assess_strato_readonly import main
    path = access_file(tmp_path)
    output = path if same_destination else tmp_path / "existing-report.json"
    if not same_destination:
        output.write_text("original report")
    before = output.read_bytes()
    monkeypatch.setattr("sys.argv", ["assessment", "--credential-file", str(path), "--output", str(output)])
    assert main() == 2
    assert output.read_bytes() == before
    assert SENTINEL not in capsys.readouterr().out


def test_successful_linux_discovery_does_not_authorize_windows_hosting(tmp_path, monkeypatch):
    import scripts.assess_strato_readonly as module
    path = access_file(tmp_path)
    calls = []
    class Client:
        def load_host_keys(self, path): pass
        def set_missing_host_key_policy(self, policy): pass
        def connect(self, **kwargs): pass
        def open_sftp(self):
            # No API for reading, downloading, listing or modifying files.
            return SimpleNamespace(close=lambda: None)
        def close(self): pass
    def execute(client, label):
        calls.append(label)
        if label == "os_family": return 0, "Linux"
        if label == "uid": return 0, "1001"
        if label == "postgres_client": return 0, "psql (PostgreSQL) 18.6 " + SENTINEL
        return 1, SENTINEL
    monkeypatch.setattr(module, "execute", execute)
    result = assess(path, SimpleNamespace(SSHClient=Client, MissingHostKeyPolicy=object), trust_file(tmp_path))
    assert result["status"] == "COMPLETED_READ_ONLY_DISCOVERY"
    assert result["findings"]["os_family"]["value"] == "Linux"
    assert result["findings"]["uid"]["value"] is False
    assert result["findings"]["postgres_client"]["version"] == "18.6"
    assert result["hosting_entitlement_verified"] is False
    assert result["isolated_windows_pilot_suitability"] == "UNVERIFIED"
    assert "windows_os" not in calls
    assert set(calls) == set(module.COMMANDS) - {"windows_os"}
    assert SENTINEL not in json.dumps(result)


def test_missing_all_trust_records_blocks_before_connection(tmp_path):
    class Forbidden:
        def SSHClient(self): pytest.fail("Missing trust cannot authorize authentication")
    result = assess(access_file(tmp_path), Forbidden(), known_hosts_path=tmp_path/'absent')
    assert result["error_code"] == "SSH_HOST_KEY_NOT_FOUND"
    assert result["failing_stage"] == "host_key_provenance"
    assert result["connection_authenticated"] is False


@pytest.mark.parametrize("change", [
    {"expected_sha256": "unknown"}, {"source_kind": "unverified_keyscan"},
    {"source_reference": ""}, {"endpoint_confirmed": False},
    {"verified_at": "not-a-date"}, {"verified_at": "2999-01-01T00:00:00Z"},
])
def test_host_key_evidence_requires_independent_endpoint_bound_receipt(tmp_path, change):
    with pytest.raises(AssessmentError) as error:
        load_host_key_evidence(trust_file(tmp_path, **change))
    assert error.value.code == "HOST_KEY_EVIDENCE_INVALID"


def test_credential_pin_conflict_never_connects_or_overwrites_file(tmp_path):
    path = access_file(tmp_path, host_key_sha256="SHA256:" + "B"*43)
    original = path.read_bytes()
    class Forbidden:
        def SSHClient(self): pytest.fail("Conflicting trust receipt cannot authorize authentication")
    result = assess(path, Forbidden(), trust_file(tmp_path))
    assert result["error_code"] == "HOST_KEY_EVIDENCE_CONFLICT"
    assert path.read_bytes() == original


def test_cli_never_overwrites_independent_trust_receipt(tmp_path, monkeypatch, capsys):
    from scripts.assess_strato_readonly import main
    path = access_file(tmp_path)
    trust = trust_file(tmp_path)
    before = trust.read_bytes()
    monkeypatch.setattr("sys.argv", ["assessment", "--credential-file", str(path), "--host-key-evidence", str(trust), "--output", str(trust)])
    assert main() == 2
    assert trust.read_bytes() == before
    assert "UNSAFE_REPORT_DESTINATION" in capsys.readouterr().out


def test_transport_diagnostics_cannot_print_remote_banners(tmp_path, capsys):
    import logging
    class Client:
        def set_log_channel(self, value): self.channel = value
        def set_missing_host_key_policy(self, policy): pass
        def connect(self, **kwargs):
            logging.getLogger(self.channel).error(SENTINEL)
            raise RuntimeError(SENTINEL)
        def close(self): pass
    result = assess(access_file(tmp_path), SimpleNamespace(SSHClient=Client, MissingHostKeyPolicy=object), trust_file(tmp_path))
    assert result["error_code"] == "SSH_ASSESSMENT_FAILED"
    assert SENTINEL not in json.dumps(result)
    captured = capsys.readouterr()
    assert SENTINEL not in captured.out + captured.err


def cached_line(host="synthetic.invalid", value=b"x", marker=""):
    blob = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + value*32
    return marker + host + " ssh-ed25519 " + base64.b64encode(blob).decode() + "\n", blob


@pytest.mark.parametrize("hashed,port", [(False,22),(True,22),(False,2222),(True,2222)])
def test_exact_or_hashed_endpoint_pin_is_usable_without_independent_receipt(tmp_path, hashed, port):
    target = 'synthetic.invalid' if port==22 else '[synthetic.invalid]:2222'
    if hashed:
        salt=b'synthetic salt'
        target='|1|'+base64.b64encode(salt).decode()+'|'+base64.b64encode(hmac.new(salt,target.encode(),hashlib.sha1).digest()).decode()
    line,blob=cached_line(target)
    cache=tmp_path/'known_hosts';cache.write_text(line)
    expected='SHA256:'+base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')
    assert known_host_pins(cache,'synthetic.invalid',port)=={expected}
    # Accept existing key, reject changed server key; never persist a replacement.
    module=SimpleNamespace(MissingHostKeyPolicy=object)
    policy=policy_for(module,known_host_pins(cache,'synthetic.invalid',port))
    policy.missing_host_key(object(),'synthetic.invalid',SimpleNamespace(asbytes=lambda:blob))
    with pytest.raises(AssessmentError):
        policy.missing_host_key(object(),'synthetic.invalid',SimpleNamespace(asbytes=lambda:b'changed server key'))
    assert cache.read_text()==line


@pytest.mark.parametrize("case,code", [
    ('wrong_host','SSH_HOST_KEY_NOT_FOUND'),('wrong_port','SSH_HOST_KEY_NOT_FOUND'),
    ('revoked','SSH_HOST_KEY_REVOKED'),('revoked_wildcard','SSH_HOST_KEY_REVOKED'),
    ('conflict','SSH_TRUST_RECORD_AMBIGUOUS'),('negated','SSH_HOST_KEY_NOT_FOUND'),
    ('malformed','SSH_TRUST_RECORD_INVALID'),('certificate_authority','SSH_TRUST_RECORD_UNSUPPORTED')])
def test_unusable_target_trust_never_falls_back_to_accepting_a_key(tmp_path,case,code):
    line,_=cached_line()
    if case=='wrong_host':line,_=cached_line('unrelated.invalid')
    if case=='wrong_port':line,_=cached_line('[synthetic.invalid]:2222')
    if case=='revoked':line,_=cached_line(marker='@revoked ')
    if case=='revoked_wildcard':line+=cached_line('*.invalid',marker='@revoked ')[0]
    if case=='conflict':line+=cached_line(value=b'y')[0]
    if case=='negated':line,_=cached_line('synthetic.invalid,!synthetic.invalid')
    if case=='malformed':line='synthetic.invalid ssh-ed25519 malformed\n'
    if case=='certificate_authority':line,_=cached_line(marker='@cert-authority ')
    cache=tmp_path/'known_hosts';cache.write_text(line)
    with pytest.raises(AssessmentError) as error:known_host_pins(cache,'synthetic.invalid',22)
    assert error.value.code==code


def test_cached_tofu_trust_is_distinguished_from_provider_verification(tmp_path):
    cache=tmp_path/'known_hosts';cache.write_text(cached_line()[0])
    class Client:
        def set_missing_host_key_policy(self,policy):pass
        def connect(self,**kwargs):pass
        def open_sftp(self):return SimpleNamespace(close=lambda:None)
        def exec_command(self,*args,**kwargs):raise RuntimeError(SENTINEL)
        def close(self):pass
    result=assess(access_file(tmp_path),SimpleNamespace(SSHClient=Client,MissingHostKeyPolicy=object),known_hosts_path=cache)
    assert result['cached_endpoint_pin_usable'] is True
    assert result['trust_basis']=='previously_established_tofu'
    assert result['independent_host_key_evidence_supplied'] is False
    assert result['provider_identity_independently_verified'] is False
    assert result['connection_authenticated'] is True
    assert SENTINEL not in json.dumps(result)
