# Arbeitsplan Vertragsregister

Phase 7 U015: financial inventory/history, calendar estimates and create-only Excel implemented; full verification in progress. [Definitions, migration and verification](PHASE7_FINANCE_DATES_EXCEL.md). D08-D10 and production acceptance remain pending.

**Stand: 21. Oktober 2026**\
**Projektstatus: F1–F15 als Prototyp vorhanden; Phasen 1–6 technisch geprüft, einschließlich eingeschränkter PostgreSQL-Logins, Dokumentwiederherstellung, zuverlässiger v2-Synchronisierung und erfolgreicher CI mit ClamAV. Produktivfreigabe und fachliche Entscheidungen offen.**

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
| 7 | Finanzhistorie, Datums- und Excel-Regeln | Nicht begonnen |
| 8–9 | Bedienoberfläche, Verfügbarkeit und Betrieb | Nicht begonnen |
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
