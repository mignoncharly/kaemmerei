"""Opt-in SSH/SFTP metadata assessment. No remote writes or application file reads.

Uses an already installed Paramiko; never installs dependencies or saves host keys.
Passwords are read only from the operator's protected file, never from CLI arguments.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import hashlib
import hmac
import json
import logging
from pathlib import Path
import re
import socket
import sys


class AssessmentError(Exception):
    def __init__(self, code):
        self.code = code


def load_access(path):
    try:
        raw = Path(path).read_bytes()
    except OSError:
        raise AssessmentError("CREDENTIAL_FILE_UNREADABLE") from None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AssessmentError("CREDENTIAL_FILE_INVALID_JSON") from None
    if not isinstance(data, dict):
        raise AssessmentError("CREDENTIAL_SCHEMA_INVALID")
    # Explicit schema: never guess an endpoint from prose or unrelated fields.
    if set(data) - {"host", "port", "username", "password", "host_key_sha256"}:
        raise AssessmentError("CREDENTIAL_SCHEMA_INVALID")
    host = data.get("host")
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]{0,252}", host):
        raise AssessmentError("CREDENTIAL_SCHEMA_INVALID")
    for key in ("username", "password"):
        if not isinstance(data.get(key), str) or not data[key] or "\x00" in data[key]:
            raise AssessmentError("CREDENTIAL_SCHEMA_INVALID")
    port = data.get("port", 22)
    if type(port) is not int or not 1 <= port <= 65535:
        raise AssessmentError("CREDENTIAL_SCHEMA_INVALID")
    pin = data.get("host_key_sha256")
    if pin is not None and (not isinstance(pin, str) or not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", pin)):
        raise AssessmentError("CREDENTIAL_SCHEMA_INVALID")
    return dict(data, port=port)


def fingerprint(key):
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")


def load_host_key_evidence(path):
    """An operator-supplied independent receipt, never a key learned on this connection."""
    if path is None or not Path(path).is_file():
        raise AssessmentError("HOST_KEY_PROVENANCE_UNVERIFIED")
    try:
        data = json.loads(Path(path).read_bytes())
        allowed = {"expected_sha256", "source_kind", "source_reference", "verified_at", "endpoint_confirmed"}
        if not isinstance(data, dict) or set(data) != allowed:
            raise ValueError()
        if not isinstance(data["expected_sha256"], str) or not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", data["expected_sha256"]):
            raise ValueError()
        if data["source_kind"] not in {"provider_public", "provider_support", "trusted_console", "prior_independently_verified_record"}:
            raise ValueError()
        if not isinstance(data["source_reference"], str) or not data["source_reference"].strip():
            raise ValueError()
        observed = datetime.fromisoformat(data["verified_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or observed > datetime.now(timezone.utc) or data["endpoint_confirmed"] is not True:
            raise ValueError()
        return data
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise AssessmentError("HOST_KEY_EVIDENCE_INVALID") from None


def known_host_pins(path, host, port):
    """Only exact or OpenSSH-hashed endpoint matches; never return other hosts."""
    target = host if port == 22 else f"[{host}]:{port}"
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        raise AssessmentError("SSH_HOST_KEY_NOT_FOUND") from None
    except (OSError, UnicodeError):
        raise AssessmentError("SSH_TRUST_RECORD_UNREADABLE") from None
    pins, by_algorithm = set(), {}
    for line in lines:
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        marker = fields.pop(0) if fields[0].startswith("@") else None
        if not fields:
            continue
        entries = fields[0].split(",")
        if any(e.startswith("!") and fnmatchcase(target, e[1:]) for e in entries):
            continue
        matched = False
        for entry in entries:
            if entry == target:
                matched = True
            elif marker == "@revoked" and fnmatchcase(target, entry):
                matched = True
            elif entry.startswith("|1|"):
                try:
                    _, _, salt, digest = entry.split("|")
                    actual = hmac.new(base64.b64decode(salt, validate=True), target.encode(), hashlib.sha1).digest()
                    matched = hmac.compare_digest(actual, base64.b64decode(digest, validate=True))
                except (ValueError, TypeError):
                    continue
            if matched:
                break
        if not matched:
            continue
        if marker == "@revoked":
            raise AssessmentError("SSH_HOST_KEY_REVOKED")
        if marker is not None:
            raise AssessmentError("SSH_TRUST_RECORD_UNSUPPORTED")
        try:
            algorithm = fields[1]
            if algorithm not in {"ssh-ed25519", "ssh-rsa", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"}:
                raise ValueError()
            blob = base64.b64decode(fields[2], validate=True)
            length = int.from_bytes(blob[:4], "big")
            if len(blob) > 16384 or blob[4:4+length] != algorithm.encode() or len(blob) <= 4+length:
                raise ValueError()
            if algorithm == "ssh-ed25519" and (len(blob) != 51 or blob[15:19] != b"\x00\x00\x00\x20"):
                raise ValueError()
            pin = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
        except (IndexError, ValueError, TypeError):
            raise AssessmentError("SSH_TRUST_RECORD_INVALID") from None
        if algorithm in by_algorithm and by_algorithm[algorithm] != pin:
            raise AssessmentError("SSH_TRUST_RECORD_AMBIGUOUS")
        by_algorithm[algorithm] = pin
        pins.add(pin)
    if not pins:
        raise AssessmentError("SSH_HOST_KEY_NOT_FOUND")
    return pins


def policy_for(paramiko, pin):
    pins = {pin} if isinstance(pin, str) else set(pin or ())
    class PinnedOrReject(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            if not pins or fingerprint(key) not in pins:
                raise AssessmentError("SSH_HOST_KEY_NOT_TRUSTED")
            # No AutoAddPolicy, file save, or implicit trust on first use.
    return PinnedOrReject()


# Fixed commands only: no credential/config-file strings are interpolated here.
# No database connections, directory listings, process arguments or service configs.
COMMANDS = {
    "os_family": "uname -s",
    "kernel_release": "uname -r",
    "uid": "id -u",
    "cpu_count": "getconf _NPROCESSORS_ONLN",
    "open_file_limit": "ulimit -n",
    "python": "python3 -I -S -B -c 'import sys; print(\"%s.%s.%s\" % sys.version_info[:3])'",
    "postgres_server_binary": "postgres --version",
    "postgres_client": "psql --version",
    "nginx": "nginx -v",
    "apache": "apache2 -v",
    "caddy": "caddy version",
    "clamav": "clamscan --version",
}
PRESENCE = ("systemctl", "supervisord", "freshclam", "age", "pg_dump", "pg_restore", "wg", "openvpn")
for _tool in PRESENCE:
    COMMANDS["available_" + _tool] = (
        "if command -v " + _tool + " >/dev/null 2>&1; then printf available; else printf unavailable; fi"
    )
COMMANDS["windows_os"] = "cmd.exe /d /c ver"


def execute(client, label):
    # Bounded output and timeout; discard stderr/stdout rather than returning raw text.
    _, out, err = client.exec_command(COMMANDS[label], timeout=8, get_pty=False)
    stdout = out.read(4096)
    stderr = err.read(4096)
    code = out.channel.recv_exit_status() if out.channel.exit_status_ready() else None
    return code, (stdout + b"\n" + stderr).decode("utf-8", "replace")


def project_value(label, code, raw):
    if code != 0:
        return {"status": "UNAVAILABLE_OR_RESTRICTED"}
    if label == "os_family":
        value = raw.strip()
        return {"status": "VERIFIED", "value": value if value in {"Linux", "FreeBSD", "OpenBSD", "Darwin", "NetBSD"} else "OTHER"}
    if label in {"uid", "cpu_count", "open_file_limit"}:
        text = raw.strip()
        if not re.fullmatch(r"\d{1,10}", text):
            return {"status": "UNVERIFIED"}
        return {"status": "VERIFIED", "value": int(text) == 0 if label == "uid" else int(text)}
    if label.startswith("available_"):
        return {"status": "VERIFIED", "available": raw.strip() == "available"} if raw.strip() in {"available", "unavailable"} else {"status": "UNVERIFIED"}
    # Return numeric versions only, never build text, hostnames, paths or banners.
    patterns = {
        "kernel_release": r"^([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
        "python": r"^(\d+\.\d+\.\d+)\s*$",
        "postgres_server_binary": r"PostgreSQL\)?\s+(\d+\.\d+(?:\.\d+)?)",
        "postgres_client": r"PostgreSQL\)?\s+(\d+\.\d+(?:\.\d+)?)",
        "nginx": r"nginx/(\d+\.\d+\.\d+)",
        "apache": r"Apache/(\d+\.\d+\.\d+)",
        "caddy": r"^v?(\d+\.\d+\.\d+)",
        "clamav": r"ClamAV\s+(\d+\.\d+\.\d+)",
        "windows_os": r"(?:Version|version)\s+(\d+\.\d+\.\d+(?:\.\d+)?)",
    }
    match = re.search(patterns[label], raw.strip())
    return {"status": "VERIFIED", "version": match.group(1)} if match else {"status": "UNVERIFIED"}


def assess(path, paramiko=None, host_key_evidence=None, known_hosts_path=None):
    report = {
        "format": "ohvr-strato-read-only-assessment-v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED", "error_code": None, "failing_stage": None,
        "connection_authenticated": False, "sftp_supported": None,
        "shell_supported": None, "findings": {},
        "remote_changes_performed": False, "application_files_read": False,
        "credential_material_recorded": False,
        "production_or_real_data_authorized": False,
        "hosting_entitlement_verified": False,
        "isolated_windows_pilot_suitability": "UNVERIFIED",
        "credential_schema_valid": False,
        "independent_host_key_evidence_supplied": False,
        "host_key_verified_before_authentication": False,
        "trust_basis": None,
        "cached_endpoint_pin_usable": False,
        "provider_identity_independently_verified": False,
    }
    client = None
    stage = "credential_validation"
    try:
        access = load_access(path)
        report["credential_schema_valid"] = True
        stage = "host_key_provenance"
        if host_key_evidence is not None and Path(host_key_evidence).is_file():
            trust = load_host_key_evidence(host_key_evidence)
            pins = {trust["expected_sha256"]}
            report["independent_host_key_evidence_supplied"] = True
            report["host_key_evidence_source_kind"] = trust["source_kind"]
            report["trust_basis"] = "operator_supplied_independent_receipt"
        else:
            known = known_hosts_path if known_hosts_path is not None else Path.home()/".ssh"/"known_hosts"
            pins = known_host_pins(known, access["host"], access["port"])
            report["cached_endpoint_pin_usable"] = True
            report["trust_basis"] = "previously_established_tofu"
        if access.get("host_key_sha256"):
            if access["host_key_sha256"] not in pins:
                raise AssessmentError("HOST_KEY_EVIDENCE_CONFLICT")
            pins = {access["host_key_sha256"]}
        stage = "dependency_validation"
        if paramiko is None:
            try:
                import paramiko
            except ImportError:
                raise AssessmentError("SSH_DEPENDENCY_UNAVAILABLE") from None
        stage = "ssh_authentication"
        # Paramiko transport-thread errors must not print raw server banners.
        logger = logging.getLogger("ohvr_strato_ssh")
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.propagate = False
        client = paramiko.SSHClient()
        if hasattr(client, "set_log_channel"):
            client.set_log_channel("ohvr_strato_ssh")
        # Enforce only previously selected exact-endpoint pins. No first-use
        # acceptance, key saves, or claim of provider verification from TOFU.
        client.set_missing_host_key_policy(policy_for(paramiko, pins))
        client.connect(hostname=access["host"], port=access["port"], username=access["username"],
                       password=access["password"], look_for_keys=False, allow_agent=False,
                       timeout=10, auth_timeout=10, banner_timeout=10)
        report["host_key_verified_before_authentication"] = True
        report["connection_authenticated"] = True
        stage = "sftp_metadata"
        try:
            sftp = client.open_sftp()
            report["sftp_supported"] = True
            try:
                statvfs = getattr(sftp, "statvfs", None)
                if statvfs:
                    v = statvfs(".")
                    report["findings"]["filesystem"] = {"status": "VERIFIED", "capacity_bytes": v.f_blocks*v.f_frsize, "available_bytes": v.f_bavail*v.f_frsize, "quota_verified": False}
            finally:
                sftp.close()
        except Exception:
            report["sftp_supported"] = None
        stage = "shell_metadata"
        try:
            code, raw = execute(client, "os_family")
            report["shell_supported"] = True
        except Exception:
            report.update(status="PARTIAL", error_code="SHELL_EXECUTION_UNAVAILABLE", failing_stage=stage, shell_supported=None)
            return report
        report["findings"]["os_family"] = project_value("os_family", code, raw)
        labels = list(COMMANDS)
        if code == 0:
            labels.remove("windows_os")
        else:
            labels = ["windows_os"]
        for label in labels:
            if label == "os_family":
                continue
            try:
                code, raw = execute(client, label)
                report["findings"][label] = project_value(label, code, raw)
            except Exception:
                report["findings"][label] = {"status": "UNAVAILABLE_OR_RESTRICTED"}
        report["status"] = "COMPLETED_READ_ONLY_DISCOVERY"
    except AssessmentError as e:
        report.update(error_code=e.code, failing_stage=stage)
    except (TimeoutError, socket.timeout):
        report.update(error_code="CONNECTION_TIMEOUT", failing_stage=stage)
    except OSError:
        report.update(error_code="CONNECTION_OR_LOCAL_ACCESS_UNAVAILABLE", failing_stage=stage)
    except Exception as e:
        # No exception text/traceback: SSH banners and auth errors can contain secrets.
        name = type(e).__name__
        code = {"AuthenticationException": "AUTHENTICATION_REJECTED", "BadHostKeyException": "SSH_HOST_KEY_MISMATCH"}.get(name, "SSH_ASSESSMENT_FAILED")
        report.update(error_code=code, failing_stage=stage)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", type=Path, default=Path(__file__).resolve().parents[2]/"secrets"/"strato-access.json")
    parser.add_argument("--host-key-evidence", type=Path, default=None,
                        help="Optional independently verified receipt; default is exact-endpoint known_hosts TOFU trust")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Credential file may never also be the report destination. Never overwrite files.
    protected = {args.credential_file.resolve()}
    if args.host_key_evidence is not None:
        protected.add(args.host_key_evidence.resolve())
    if args.output.resolve() in protected:
        print('{"error_code":"UNSAFE_REPORT_DESTINATION"}')
        return 2
    if args.output.exists():
        print('{"error_code":"REPORT_ALREADY_EXISTS"}')
        return 2
    report = assess(args.credential_file, host_key_evidence=args.host_key_evidence)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    except OSError:
        print('{"error_code":"REPORT_WRITE_UNAVAILABLE","failing_stage":"report_write"}')
        return 2
    print(json.dumps({k:report[k] for k in ("status", "error_code", "failing_stage", "connection_authenticated")}))
    return 0 if report["status"] == "COMPLETED_READ_ONLY_DISCOVERY" else 2


if __name__ == "__main__":
    sys.exit(main())
