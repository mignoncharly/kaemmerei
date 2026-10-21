# Änderungen

## 21. Oktober 2026 — Git-/CI-/Testdienst-Vorbereitung

- Projekt als lokales Git-Repository mit dem angegebenen GitHub-Ziel eingerichtet.
- Automatischen Ablauf für Testumgebung, SQLite-/PostgreSQL-Prüfungen und optionalen Push sowie getrennten Docker-Testdienst ergänzt.
- Linux-CI um JUnit-Artefakte und eingeschränktes PostgreSQL-Testkonto erweitert; keine Produktivdaten oder Produktivzugänge verwendet.
- Lokale Syntax-/Voraussetzungsprüfungen bestanden. GitHub-Netzwerkzugriff blockiert; Docker fehlt; tatsächliche Dienst-/pytest-/CI-Ausführung weiterhin offen.

## 21. Oktober 2026 — Nachbesserung Phase 1

- Testhilfen für Vertragsnummern und Archivfilter repariert; Dokumentenspeicher je Anwendungsinstanz konfiguriert.
- Isolierte synthetische Testdatenbanken mit echten Alembic-Migrationen, Standardbibliothek-Prüflauf und PostgreSQL-/CI-Konfiguration ergänzt.
- Lokale SQLite-Prüfung: 22 Prüfungen, davon 19 bestanden und drei erwartete Fehler zu offenen Befunden R01/R04/R10. Alle zehn ursprünglichen Anwendungstests bestehen.
- PostgreSQL-Prüfung durch lokalen initdb-Tokenfehler 87 blockiert; direkte pytest-/gehostete CI-Ausführung nicht nachgewiesen. Phase 1 noch nicht vollständig abgenommen.
- Ausgangslage und Prüfmatrix unter docs/PHASE1_BASELINE.md und docs/VERIFICATION_MATRIX.md dokumentiert; README, Arbeitsplan, Remediation-Plan und HANDOFF aktualisiert.

## 20. Oktober 2026

- Umsetzung der Funktionsbereiche F1–F15 für das Vertragsregister.
- Dokumentation von Funktionen, Installation und API in [README.md](README.md).
- Umsetzungs- und Freigabestatus in [docs/ARBEITSPLAN.md](docs/ARBEITSPLAN.md) aktualisiert.
