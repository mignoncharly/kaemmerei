"""Deterministic scanner solely for isolated tests, never a runtime setting."""
from app.documents import ScanResult


class CleanScanner:
    def scan(self,data):
        return ScanResult('clean','synthetic-test-scanner')
