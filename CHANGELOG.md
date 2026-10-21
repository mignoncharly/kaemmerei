# Änderungen

## 21. Oktober 2026 — Native PostgreSQL-Testinstanz

- Lokale Einrichtung standardmäßig auf native PostgreSQL-Binärdateien umgestellt; Docker bleibt optional.
- Separate gekennzeichnete Testinstanz, private Passdateien, eingeschränktes Testkonto und Start-/Stoppbefehle ergänzt. Bestehender Windows-Dienst unverändert.
- Zehn Sicherheitsprüfungen für den nativen Manager bestanden; neue native Linux-CI-Prüfung ergänzt. Windows-Start in der verwalteten Sitzung durch verweigerte Ordnerrechte blockiert; erste Einrichtung in normaler autorisierter PowerShell erforderlich.
- CI-Lauf 39575414353 erfolgreich: native PostgreSQL-Einrichtung ohne Docker einschließlich Migrationen/pytest/Stopp sowie bisherige SQLite-/PostgreSQL-18-Jobs bestanden. Nachweis in HANDOFF U008 und docs/evidence/native-postgresql-ci-39575414353.json.

## 21. Oktober 2026 — Veröffentlichung und erfolgreicher Linux-CI-Nachweis

- Quellstand d9e39e5 auf main im angegebenen GitHub-Repository veröffentlicht.
- GitHub-Actions-Lauf 39571113046 erfolgreich: SQLite-/PostgreSQL-Prüfungen und direkte pytest-Ausführung, beide JSON-/JUnit-Artefakte vorhanden.
- Technisches Prüftor von Phase 1 geschlossen; R01/R04/R10 bleiben erwartete Fehler. Keine Produktivfreigabe.
- Docker-Installation auf dem lokalen Host und GitHub-Branch-Schutz bleiben getrennte Host-/Kontoeinrichtung; Nachweise und aktueller Stand in HANDOFF U006.

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
