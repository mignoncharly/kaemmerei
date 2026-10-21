"""Run the baseline, migration/configuration and security regression checks.

Usage: python scripts/verify_phase1.py --database sqlite|postgresql
PostgreSQL requires TEST_POSTGRES_ADMIN_URL pointing to a LOCAL disposable
cluster's postgres administrative database. Each test creates/drops its own DB.
Exit 0 means the verification foundation passed, not production acceptance.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", choices=("sqlite", "postgresql"), default="sqlite")
    args = parser.parse_args()
    os.environ["VERIFICATION_DATABASE"] = args.database
    scratch = ROOT / ".verification" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(scratch)
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_phase1")
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    report = {"backend": args.database, "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
              "unexpected_successes": len(result.unexpectedSuccesses),
              "known_open_checks": [test.id() for test, _ in result.expectedFailures],
              "successful_verification_foundation": result.wasSuccessful(),
              "production_accepted": False}
    output = ROOT / ".verification" / f"phase1-{args.database}.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Backend: {args.database}; expected failures are OPEN findings, not fixes.")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
