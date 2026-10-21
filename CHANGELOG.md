# Änderungen

## 21. Oktober 2026 — Phase 3: Datenbankintegrität und RLS

- P03-T01–T08: Vorab-Inventur, Constraints und fehlender Tax-Reviewer-Fremdschlüssel; keine stillen Datenkorrekturen.
- Getrennte Betreiber-, Web-, Integrations-, Wartungs- und NOLOGIN-Auditrollen; FORCE RLS mit Elternbezug und transaktionslokaler, bei jedem neuen Transaktionsbeginn validierter Identität.
- Eng begrenzte Passwortauflösung und Vertragssperre; keine allgemeinen Credential-Leserechte für Integrationen. Append-only Audit mit Akteur, Ziel, Ergebnis und Korrelations-ID.
- Echte PostgreSQL-LOGIN-Tests prüfen ungefilterte SQL-Abfragen, Pool-Wiederverwendung, Widerruf, Freigabezuweisung, Wartungsrechte und Auditmanipulation. SQLite bleibt ausdrücklich ohne RLS.
- Neue Migrationen 0015/0016 ausschließlich an synthetischen Datenbanken geprüft. Keine Produktivmigration oder Freigabe. Nachweise und Einrichtung: docs/PHASE3_DATABASE_SECURITY.md und HANDOFF U011.

## 21. Oktober 2026 — Phase 2: Berechtigungen und Identitäten

- P02-T01–T08 umgesetzt: zentrale Zugriffsabfragen, explizite Freigabefähigkeit, Empfängerteams/Mitgliedschaften und konkrete Prüfzuweisung ohne automatische Leserechtsausweitung.
- Fachbereiche und Kontakte administrierbar; Deaktivierung, Sitzungswiderruf, scoped Token-Sperre und historische Anzeigenamen abgesichert.
- Passwortwechsel mit bisherigem Passwort, CSRF, Ratenbegrenzung und Sitzungsrotation; administrative/CLI-Wiederherstellung erzwingt Passwortwechsel. Gemeinsame Validierung und nebenläufigkeitssicherer Schutz des letzten Administrators.
- Additive Migration 0014 nur in isolierten Testdatenbanken geprüft; keine Geschäftsdatenbank migriert. Kontakt-Backfill bleibt fachbereichsbezogen; keine automatischen Freigaberechte oder Prüfzuweisungen.
- Lokal PostgreSQL: 66 Tests bestanden; SQLite: 65 bestanden und ein PostgreSQL-spezifischer Skip; jeweils 15 Unterprüfungen bestanden. Alle drei CI-Jobs für 9fde6c0 in Lauf 39594698525 erfolgreich. Details: docs/PHASE2_AUTHORIZATION.md und HANDOFF U010.
- CLI-Enginefreigabe bei Fehlern korrigiert; Testdatenbankbereinigung verwendet geprüfte normale DROP-Operationen ohne Sitzungsbeendigung oder erweiterte Rollenrechte. Keine Produktivfreigabe.

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
