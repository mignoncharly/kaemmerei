# Arbeitsplan Vertragsregister

U023 local candidate `af290a4`: PostgreSQL 362 passed/2 skips, SQLite 328 passed/36 skips, 15 subtests each; representative mixed load and encrypted recovery passed. [Final evidence and exact remaining actions](U023_CANDIDATE_VERIFICATION.md). Earlier connection-timeout failure retained. Hosted CI/actual native patch, browser/scanner/host and participant gates remain open; no real-data or production authorization.

U022 final local verification: implementation `05648ed`, PostgreSQL 343 passed/2 skips, SQLite 309 passed/36 skips, 15 subtests each; full representative mixed workload and encrypted restore passed. [Exact evidence, scope and remaining release gates](U022_ENGINEERING_VERIFICATION.md). Synthetic scope approval is separate from actual-host/participant acceptance and real-data/production authorization.

U022: [pilot decisions](PILOT_DECISIONS.md) recorded; technical work continues on
local monitoring/job evidence, bounded event publication, mixed workloads and
representative encrypted recovery. Versioned pending [domain requirements](DOMAIN_RULE_REQUIREMENTS.md),
read-only [STRATO assessment](HOSTING_ASSESSMENT.md) and [release/recovery runbook](RELEASE_RUNBOOK.md)
prepared. Four separate release statuses apply; no real-data/production
authorization. Current evidence/environment limitations are in HANDOFF U022.

Phase 9 U017 checkpoint: bounded ingress, shared database throttling, synchronous request workers, capacity/TLS checks and correlation implemented in b962824, with parser/path guards and patched compatible dependencies in 1649b15. [Controls, limits and remaining operations work](PHASE9_OPERATIONS.md). All five hosted jobs passed for 1649b15; Phase 9 exit and production deployment remain open.

Phase 8 U016: frontend/navigation technically verified for 6ebcaad: 178 collected; PG 176 passed + 2 local skips, SQLite 160 passed + 18; eight Phase 8 tests pass on both backends, all five hosted jobs including Chromium passed. [Behavior, browser constraints and evidence](PHASE8_FRONTEND_NAVIGATION.md). Production and usability acceptance remain pending.

Phase 7 U015: financial inventory/history, calendar estimates and create-only Excel technically verified: 170 collected; PG 168 passed + 2 local skips; SQLite 152 passed + 18; 15 subtests each. Phase 7 restricted PostgreSQL 19 passed; all four hosted jobs passed for 2fd1bf8. [Definitions, migration and verification](PHASE7_FINANCE_DATES_EXCEL.md). D08-D10 and production acceptance remain pending.

**Stand: 21. Oktober 2026**\
**Projektstatus: F1-F15 als Prototyp vorhanden; Phasen 1-8 technisch geprüft, einschließlich eingeschränkter PostgreSQL-Logins, Dokumentwiederherstellung, API-v2-Synchronisierung, Finanzhistorie und realer Browser-CI. Produktivfreigabe, manuelle Bedien-/Screenreader-Abnahme und fachliche Entscheidungen offen.**

## Ziel

Das Vertragsregister bündelt die Erfassung, Pflege, Suche und Auswertung kommunaler Verträge. Die vollständige Funktionsübersicht, Bedienung, Startanleitung und API-Beschreibung stehen im [README](../README.md). Diese Datei hält den Umsetzungsstand und die noch erforderlichen Entscheidungen fest.

## Umsetzungsstand

Die 15 priorisierten Funktionsbereiche sind im Prototyp vorhanden. Dazu gehören die Vertragsverwaltung, Dokumente und DMS-Verknüpfungen, Fachbereiche und Benutzerrollen, Fristen, Aufgaben, Änderungshistorie, Finanz- und §-2b-Prüfdaten, Prüf- und Freigabeschritte, Excel-Import/-Export, Berichte und die schreibgeschützte JSON-API. Die Codeprüfung hat offene Berechtigungs-, Workflow-, Datenintegritäts- und Betriebsprobleme festgestellt. Eine pauschale Fertigstellung oder Produktivreife ist daraus nicht ableitbar.

Die lokale Anwendung nutzt SQLite und kann über versionierte Alembic-Migrationen aktualisiert werden. Die bestehende API stellt einen technischen Anschluss bereit, ersetzt aber keinen systemspezifischen Adapter.

## Nachbesserung und Prüfstand

Der verbindliche technische Aufgabenbestand mit R01–R41, Aufgabenkennungen und Abnahmekriterien steht in [REMEDIATION PLAN PHASES.md](../REMEDIATION%20PLAN%20PHASES.md). [HANDOFF.md](../HANDOFF.md) dokumentiert jede Arbeitsänderung und den aktuellen Zustand. Fachliche Entscheidungen D01–D13 sind Vorschläge und noch nicht als städtisch freigegeben dokumentiert.

| Phase | Inhalt | Stand |
|---|---|---|
| 1 | Ausgangslage, Testreparaturen, isolierte Speicher und echte Migrationstests | Lokal PostgreSQL: 44 bestanden, keine Fehler/Skips/Xfails; SQLite: 43 bestanden, ein PostgreSQL-spezifischer Skip. R01/R04/R10 behoben. Aktueller CI-Nachweis im Abnahmebericht. |
| 2 | Anwendungsberechtigungen und Identitäten | P02-T01–T08 implementiert und lokal SQLite/PostgreSQL geprüft; technische Rollenmatrix und CI-Nachweis in PHASE2_AUTHORIZATION.md. Fachliche Freigabe bleibt offen. |
| 3 | Datenbankrollen, Constraints, RLS und geschützte Auditablage | P03-T01–T08 technisch verifiziert: PostgreSQL 81 bestanden, SQLite 69 + 12 PG-Skips, drei CI-Jobs erfolgreich; DBA-/Produktivfreigabe offen. [Phase 3](PHASE3_DATABASE_SECURITY.md) |
| 4 | Versionsgebundene Freigaben, Archivschutz, Nebenläufigkeit | P04-T01–T08 technisch verifiziert: PostgreSQL 99 bestanden, SQLite 87 + 12 PG-Skips, 18 Workflow-/Rennprüfungen und drei CI-Jobs erfolgreich. D04 fachlich offen. [Phase 4](PHASE4_WORKFLOW.md) |
| 5 | Dokumentensicherheit und Speicherlebenszyklus | P05-T01–T08 technisch verifiziert: PostgreSQL 128 bestanden + 2 lokale Skips, SQLite 116 + 14 Skips; CI 39613990793 erfolgreich mit echter ClamAV-Prüfung. [Phase 5](PHASE5_DOCUMENT_LIFECYCLE.md). D05/D06 und Produktivfreigabe offen. |
| 6 | Zuverlässige API-Synchronisierung und Token-Verantwortung | P06-T01–T08 technisch verifiziert: PostgreSQL 149 + 2 lokale Skips, SQLite 134 + 17 Skips; 21 PG-Synchronisationsprüfungen und vier CI-Jobs erfolgreich. [Phase 6](PHASE6_INTEGRATION_SYNC.md). v1 bleibt verfügbar; D07 fachlich offen. |
| 7 | Finanzhistorie, Datums- und Excel-Regeln | P07-T02-T09 technisch geprüft, einschließlich historischer Fachbereichszuordnung, unbekannter Werte und atomarer Importidentität. P07-T01/D08-D10 fachlich offen. [Phase 7](PHASE7_FINANCE_DATES_EXCEL.md) |
| 8 | Bedienoberfläche und Navigation | P08-T01-T09 technisch geprüft für 6ebcaad: PostgreSQL 176 + 2 lokale Skips, SQLite 160 + 18; acht Phase-8-Prüfungen je Backend und fünf CI-Jobs einschließlich Chromium erfolgreich. [Phase 8](PHASE8_FRONTEND_NAVIGATION.md). Manuelle Bedien-/Screenreader-Abnahme offen. |
| 9 | Verfügbarkeit und Betrieb | In Bearbeitung (U017): request limits/shared throttling/workers; scheduling, workload, encrypted recovery, alerting, D11/D12 and production acceptance open. [Phase 9](PHASE9_OPERATIONS.md) |
| 10 | Fachliche/technische Abnahme, Pilot und expliziter Integrationsumfang | Nicht begonnen |

Die [Prüfmatrix](VERIFICATION_MATRIX.md) benennt Rollen, Direktzugriffe, Kindobjekte und noch fehlende Prüfungen. [PHASE1_BASELINE.md](PHASE1_BASELINE.md) hält Umgebung, Befehle, Ergebnisse und Einschränkungen fest. Fachbereichsfremde Filterwerte (R01), veränderbare archivierte Prüfvorgänge (R04) und Zugriff bei deaktiviertem Fachbereich (R10) sind korrigiert und auf SQLite sowie PostgreSQL geprüft. Weitere Befunde werden in den jeweiligen Phasen behoben und geprüft.

Der ursprüngliche PostgreSQL-/pytest-CI-Nachweis bleibt im [Linux-CI-Lauf 39571113046](https://github.com/mignoncharly/kaemmerei/actions/runs/39571113046) erhalten. Der native Windows-Testcluster ist inzwischen initialisiert und erreichbar. In dieser Sitzung wurden echte Anwendungsoperationen und Migrationen in neu angelegten PostgreSQL-Testdatenbanken ausgeführt. Reguläre Vertragsdaten wurden weder verwendet noch migriert. Docker ist lokal nicht erforderlich; Hauptbranch-Schutzregeln bleiben getrennte Kontoeinrichtung. Aktueller CI-Stand und die verbleibende ACL-Grenze der Agentenumgebung stehen im Abnahmebericht.

## Noch zu klären

- Verbindliche Pflichtfelder, Kataloge und fachliche Bedeutung der Vertragsdaten.
- Verantwortlichkeiten von Kämmerei, Fachbereichen und IT; Regeln für Rollen und Vertretungen.
- Datenschutz, Aufbewahrungs- und Löschregeln, Protokollierung sowie Umgang mit Vertragsdateien.
- Zielsysteme für eine direkte H&H-, DMS- oder Benutzerverzeichnis-Synchronisierung und die dafür verfügbaren APIs, Zugangsdaten und Testumgebungen.
- Anforderungen an E-Mail- oder Push-Erinnerungen sowie gegebenenfalls eine Beschaffungsintegration.
- Hosting, Netzwerkzugriff, Backups, Wiederherstellung, Monitoring und Updatebetrieb.

## Nächste Schritte vor einem Produktivbetrieb

1. Fachseite prüft die Pflichtfelder, Statusabläufe und Auswertungen anhand bereinigter Vertragsbeispiele.
2. IT und Datenschutz legen Betriebs-, Berechtigungs-, Speicher- und Sicherungskonzept fest.
3. Für jedes gewünschte Zielsystem dessen technische Dokumentation und Testzugang beschaffen; danach den konkreten Adapter planen.
4. Interne Serverumgebung mit HTTPS, PostgreSQL, Backups und Wiederherstellungstest einrichten.
5. Berechtigungs-, Sicherheits- und Abnahmetests durchführen und den Pilotbetrieb mit benannten Fachbereichen freigeben.

## Abgrenzung

Die vorhandene Schnittstellen-API liest Vertragsdaten und Dokumente, nimmt aber keine Änderungen entgegen. H&H-, LDAP/SSO- und produktspezifische DMS-Konnektoren, externe Benachrichtigungen und die automatische Übernahme von Dokumenten sind noch nicht integriert. Der §-2b-Prüfbereich dokumentiert Status und Ergebnis; er ersetzt keine fachliche oder rechtsverbindliche Prüfung.

Die Anwendung ist eine Arbeitsversion und noch keine freigegebene kommunale Produktivlösung. Code allein ersetzt keine fachliche Abnahme, Datenschutz- oder Sicherheitsfreigabe.

Phase 9 U018 continues with durable scan batches, review-only native Windows operations templates, approved workload/recovery targets and statement-scoped RLS/read optimizations (head 0022). Initial workload failures are preserved in docs/evidence/phase9-workload-before.json. Full current-source verification and remaining MFA/backup/deployment gates are tracked in HANDOFF.md and docs/PHASE9_OPERATIONS.md. No Phase 9 exit or deployment acceptance.

Phase 9 U019 implements the approved local TOTP strategy: encrypted user-bound seeds, operator-authorized enrollment/recovery, short pending challenges, persisted replay protection, PostgreSQL enforcement and separate service credentials. Head 0023; full SQLite 244 collected: 219 passed + 25 explicit skips, 15 passing subtests. Full PostgreSQL and exact-source hosted verification are running; no production rollout or Phase 9 exit. See HANDOFF U019 and docs/PHASE9_OPERATIONS.md.

U019 final checkpoint ece7797: 244 collected; native PostgreSQL 242 passed/2 local skips; SQLite 219 passed/25 explicit skips; 15 passing subtests each; explicit PostgreSQL 23 passed. All five exact-source hosted jobs passed (39656369586). TOTP implementation technically verified; production custody/deployment and the remaining Phase 9 gates remain open. Evidence in HANDOFF U019 and docs/evidence/phase9-u019-local.json.


U020 Phase 9: verschluesselte/signierte PostgreSQL-/Dokumentsicherung und
verifiziertes neues Wiederherstellungsbuendel implementiert; kein Import in
bestehende Datenbanken, keine Aktivierung produktiver Aufgaben oder Schluessel-
hinterlegung. 29 gezielte Tests erfolgreich; vollstaendige/CI-Nachweise folgen
in HANDOFF. Vorgeschlagene IT-Betriebs-/Identitaetsrollen sind vorlaeufig und nur
fuer Produktion; lokale Entwicklung, Anmeldung und Wiederherstellung brauchen
keine kommunale Freigabe. Phase 9 bleibt offen.


U020 final checkpoint 92329b6: 262 collected; native PG 260 passed/2 local skips,
SQLite 236/26 explicit skips, 15 passing subtests each; explicit PG 24 passed;
backup/Windows 29 passed. All 17 backup cases executed on PG. All five exact-
source hosted jobs passed (39660619585). Final catalog 0 guarded DBs/0 generated
roles, control privileges unchanged. Encrypted restore technically verified on
tiny synthetic data; no production schedule/escrow/deployment or RPO/RTO
acceptance. Phase 9 remains open. Details and remaining follow-ups: HANDOFF U020,
docs/PHASE9_OPERATIONS.md and docs/evidence/phase9-u020-local.json.


U021: continuing Phase 9 entry work before Phase 10. Standalone DBA TLS gap
fixed; hash-pinned 30-package runtime and deterministic committed-source release
builder/manifest/verifier added. Fresh Windows installation/pip check and 29
targeted release/TLS tests passed. Packaged runtime, full tests and eight-job
current-source hosted evidence pending in HANDOFF. No production deployment or
Phase 9 exit; local development has no municipal approval dependency.


Phase 10 preparation: [acceptance worksheet](PHASE10_ACCEPTANCE.md) maps
F1-F15 to actual journeys/permissions/regressions and records connector, owner,
pilot and release gaps. This is preparation only: Phase 9 entry gates remain
open; no production release, named appointment or external workflow is activated.


U021 final verification (source 3442ad8): 292 collected; serial native PostgreSQL
290 passed/2 expected local skips; SQLite 266/26 explicit skips; 15 subtests each.
Explicit PostgreSQL 24 passed; release/operator/YAML 30 passed. All eight hosted
jobs passed, including pure Windows/Linux packaged runtime and byte comparison.
Final catalog 0 guarded DBs/0 generated roles; control privileges unchanged.
Phase 10 F1-F15 matrix prepared (P10-T02); Phase 9 and production release gates
remain open. Details/evidence/failure history: HANDOFF U021 and PHASE9_OPERATIONS.
