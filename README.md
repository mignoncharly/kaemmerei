# OPEN.HERZ Vertragsregister

U022: [approved synthetic pilot decisions](docs/PILOT_DECISIONS.md),
[pending versioned domain requirements](docs/DOMAIN_RULE_REQUIREMENTS.md),
[STRATO investigation](docs/HOSTING_ASSESSMENT.md) and [release runbook](docs/RELEASE_RUNBOOK.md).
Development, synthetic readiness, real-data pilot authorization and broader
production approval are separate. Current maintenance/monitoring and mixed-load/
recovery evidence is in HANDOFF U022; no deployment or external push is authorized.

Phase 9 U017 checkpoint: bounded ingress, shared database throttling, synchronous request workers, capacity/TLS checks and correlation implemented in b962824, with parser/path guards and patched compatible dependencies in 1649b15. [Controls, limits and remaining operations work](docs/PHASE9_OPERATIONS.md). All five hosted jobs passed for 1649b15; Phase 9 exit and production deployment remain open.

Phase 8 U016: frontend/navigation technically verified for 6ebcaad: 178 collected; PG 176 passed + 2 local skips, SQLite 160 passed + 18; eight Phase 8 tests pass on both backends, all five hosted jobs including Chromium passed. [Behavior, browser constraints and evidence](docs/PHASE8_FRONTEND_NAVIGATION.md). Production and usability acceptance remain pending.

Phase 7 U015: financial inventory/history, calendar estimates and create-only Excel technically verified: 170 collected; PG 168 passed + 2 local skips; SQLite 152 passed + 18; 15 subtests each. Phase 7 restricted PostgreSQL 19 passed; all four hosted jobs passed for 2fd1bf8. [Definitions, migration and verification](docs/PHASE7_FINANCE_DATES_EXCEL.md). D08-D10 and production acceptance remain pending.

Das Vertragsregister ist eine deutschsprachige Webanwendung zur Erfassung, Suche, Verwaltung und Auswertung kommunaler Verträge. Die Anwendung läuft lokal oder kann nach technischer und fachlicher Freigabe auf einem internen Server betrieben werden.

**Projektstand:** 21. Oktober 2026 · **Umfang:** Prototypfunktionen F1–F15; Nachbesserung in zehn Phasen

> Die Anwendung ist eine Arbeitsversion. Vor einem Produktivbetrieb müssen Datenschutz, Berechtigungen, IT-Betrieb, Datensicherung und fachliche Zuständigkeiten durch die Stadt geprüft und freigegeben werden.

## Verifizierter Stand und offene Fehler

Phase 2 (P02-T01–T08) ergänzt zentrale Zugriffsabfragen, explizite Prüfzuweisungen, gepflegte Fachbereiche/Kontakte/Empfängerteams und Passwortwechsel mit Sitzungswiderruf. Lokal bestehen 66 Tests auf PostgreSQL und 65 auf SQLite (ein ausschließlich PostgreSQL-spezifischer Skip); beide Läufe haben zusätzlich 15 bestandene Unterprüfungen. Migration `0014_identity_authorization` wurde ausschließlich in isolierten Testdatenbanken geprüft. Rollenmatrix, Migrationsregeln und aktueller CI-Nachweis: [Phase 2](docs/PHASE2_AUTHORIZATION.md).

Phase 1 der [Nachbesserungsplanung](REMEDIATION%20PLAN%20PHASES.md) ist lokal gegen native PostgreSQL 18 geprüft: 44 Tests und 15 Unterprüfungen bestanden, keine Fehler, übersprungenen Tests oder erwarteten Fehler. Der SQLite-Lauf besteht mit 43 Tests; nur der ausdrücklich PostgreSQL-spezifische Lebenszyklustest wird dort übersprungen. R01, R04 und R10 sind behoben und durch reguläre Regressionstests abgesichert. Der vorhandene Windows-Testcluster funktioniert ohne Docker; der Anwender hat den nicht blockierenden Start bestätigt. Ein erneuter Startversuch aus der verwalteten Agentenumgebung scheitert an deren ACL-Berechtigungen, nicht am ursprünglichen Tokenfehler 87. Aktuelle Befehle, Einschränkungen und CI-Nachweise stehen im [Abnahmebericht](docs/PHASE1_BASELINE.md). Eine Produktivfreigabe ist damit nicht verbunden.

Phase 3 ergänzt Schema-Constraints, getrennte PostgreSQL-Laufzeitrollen, FORCE RLS, transaktionslokale Identität und geschützte Auditablage. Stand und Nachweise: [Phase 3](docs/PHASE3_DATABASE_SECURITY.md). SQLite hat keine RLS. Migrationen `0015_schema_integrity` und `0016_database_security` sind ausschließlich in synthetischen Testdatenbanken geprüft; keine Geschäftsdatenbank wurde migriert. Produktive Webprozesse benötigen getrennte `DATABASE_URL`/`INTEGRATION_DATABASE_URL` und `ENFORCE_DATABASE_SECURITY=1`; privilegierte Betreiberzugänge gehören ausschließlich in separate Prozesse.

Phase 4 ergänzt an Inhaltsrevisionen gebundene, unveränderbare Entscheidungen, unabhängige Freigabe, Aktivierungssperre, Task-/Prüfversionen, Wiederholungsschutz und gemeinsamen Archivschutz. Neue Verträge und Importe beginnen als Entwurf; eine neue Aktivierung benötigt aktuelle Freigaben aller `MANDATORY_REVIEW_RECIPIENTS` (Pilotstandard: Kämmerei). Alte Freigabe-/Steuerstände bleiben ausdrücklich ungeprüfte Altbestände. Migration `0017_bound_workflow`, Entscheidungsregeln, Betreiber-Inventur und Nachweise: [Phase 4](docs/PHASE4_WORKFLOW.md). Fachliche Entscheidung D04 bleibt offen; keine Geschäftsdatenbank wurde migriert.

Phase 5 implementiert private Quarantäne, Inhaltsprüfung und ClamAV-Anbindung, verifizierte Downloads, dauerhafte Wiederholungsaufträge, Dokumentersatz und DMS-Korrekturen mit Erhalt alter Versionen. Migration `0018_document_lifecycle` behandelt Altdokumente ausdrücklich als ungeprüft. Ohne erfolgreiche Malwareprüfung bleibt eine Datei gesperrt. Aufbewahrung und Löschung bleiben bis D06 ohne destruktive Automatik. Konfiguration, Wiederherstellung und Prüfgrenzen: [Phase 5](docs/PHASE5_DOCUMENT_LIFECYCLE.md). Lokale ClamAV-Installation und produktive Speicherrechte sind keine bereits erfolgte Bereitstellung.

Phase-5-Prüfstand: PostgreSQL 128 bestanden und 2 lokale Skips, SQLite 116 bestanden und 14 Skips; jeweils 15 Unterprüfungen bestanden. [CI 39613990793](https://github.com/mignoncharly/kaemmerei/actions/runs/39613990793) ist erfolgreich, einschließlich echter ClamAV-Prüfung mit aktuellen offiziellen Signaturen. Fachliche Entscheidungen D05/D06 und Produktivfreigabe bleiben offen.

Phase 6 ergänzt eine getrennte v2-Synchronisierung mit festem Anfangsbestand, dauerhaftem Änderungsfeed, fachbereichssicheren Entfernungsmeldungen, tokengebundenen Cursorn und ausdrücklich vergebenen Leserechten. v1 bleibt verfügbar; bestehende Tokens erhalten keine zusätzlichen v2-Rechte. Migration `0019_integration_sync`, Betreiber-/Verbraucherregeln und Nachweise: [Phase 6](docs/PHASE6_INTEGRATION_SYNC.md). D07 und Produktivfreigabe bleiben offen.

Phase-6-Prüfstand: PostgreSQL 149 bestanden und 2 lokale Skips, SQLite 134 bestanden und 17 Skips; jeweils 15 Unterprüfungen bestanden. Alle 21 PostgreSQL-Synchronisationsprüfungen und alle vier Jobs von [CI 39624468561](https://github.com/mignoncharly/kaemmerei/actions/runs/39624468561) erfolgreich. Keine Geschäftsdatenmigration oder Bereitstellung.

Die technischen Finanz-/Datums-/Excel-Korrekturen der Phase 7 sind geprüft; D08-D10 bleiben fachlich unbestätigt. Phase 8 korrigiert Frontend und Navigation mit fünf erfolgreichen CI-Jobs einschließlich realer Browserprüfung. Betriebliche Härtung und Produktivfreigabe bleiben offen.

Aktueller Zustand und jede Arbeitsänderung stehen in [HANDOFF.md](HANDOFF.md). [Prüfmatrix](docs/VERIFICATION_MATRIX.md) und [Phase-1-Nachweis](docs/PHASE1_BASELINE.md) trennen bestandene Prüfungen, bekannte Fehler und noch nicht ausgeführte Prüfungen. H&H-/LDAP-/produktspezifische DMS-Anbindungen und externe Erinnerungen bleiben ausdrücklich außerhalb des bisher gelieferten Umfangs.

## Funktionsübersicht

| Nr. | Funktion | Was die Anwendung bietet |
|---|---|---|
| F1 | Zentrale Vertragsverwaltung | Verträge anlegen, suchen, filtern, bearbeiten und archivieren. Jeder Vertrag erhält eine automatisch erzeugte Vertragsnummer. Änderungen verwenden Versionsschutz, damit eine ältere Bearbeitung keine neueren Daten überschreibt. |
| F2 | Vertragsdokumente | Private, geprüfte Downloads mit Quarantäne-/Scanstatus und Integritätsprüfung; Dateiausgabe als Download statt unkontrollierter Inline-Vorschau. Ersatzversionen und DMS-Korrekturen erhalten Vorgänger und Historie. Dateien können beim Erstellen hinzugefügt werden; ausstehende Prüfung bedeutet noch keine verfügbare Datei. |
| F3 | Fachbereichsverwaltung | Administratoren pflegen Fachbereiche, Kontakte und Empfängerteams unter „Fachbereiche & Identitäten“. Umbenennen, Deaktivieren und Reaktivieren erhalten stabile IDs und historische Anzeigenamen. Kontakte sind fachbereichsbezogen oder bewusst global geteilt. Kontakt- und Vertretungsbezeichnungen erteilen keine Zugriffsrechte. |
| F4 | Benutzer und Berechtigungen | Administratoren verwalten Konten und explizite Freigabefähigkeit. Fachbereichsnutzer bearbeiten ihren aktiven Fachbereich. Prüfer lesen alle Verträge; Entscheidungen erfordern zusätzlich aktive Teammitgliedschaft und konkrete Zuweisung. Passwortwechsel und administrative Wiederherstellung widerrufen Sitzungen; Start-/Wiederherstellungspasswörter müssen ersetzt werden. |
| F5 | Vertragsfristen | Beginn, Ende, Kündigungsfrist und automatische Verlängerung erfassen. Rechnerische Schätzungen verwenden den ursprünglichen Anker, berücksichtigen Monatsenden und schreiben gekündigte/beendete Verträge nicht fort. Kein Nachweis rechtlich zulässiger Kündigung. |
| F6 | Erinnerungen und Warnungen | Überfällige und innerhalb der nächsten 90 Tage anstehende Vertragsfristen erscheinen in der Übersicht; überfällige Aufgaben werden hervorgehoben. Es gibt keine E-Mail- oder Push-Erinnerungen. |
| F7 | Dashboard und Suche | Schnellfilter für aktive Verträge, anstehende Vertragsfristen, Entwürfe/in Bearbeitung, Verträge mit offenen Freigaben sowie gekündigte/beendete Verträge. Steuerlicher Prüfstatus ist getrennt. Seitenweise Ergebnisse mit Gesamtzahl und filtererhaltender Navigation; Standard 50, maximal 100 pro Seite. Archivierte Verträge über den Statusfilter. Persönlicher Arbeitskorb für zugewiesene Aufgaben und entscheidbare aktuelle Prüfungen. |
| F8 | Bearbeitungsstatus und Aufgaben | Je Vertrag Aufgaben für Prüfung, Vervollständigung, Aktualisierung oder sonstige Arbeiten erfassen. Aufgaben haben Titel, Beschreibung, Fälligkeit, zuständige Person und Status Offen, In Bearbeitung oder Erledigt. |
| F9 | Änderungshistorie | Vertragsänderungen mit handelndem Benutzer, Zeitpunkt und verständlich dargestellten geänderten Feldern nachvollziehen. Erstellen, Bearbeiten, Archivieren, Dokumente, Aufgaben und Prüfabläufe werden am jeweiligen Vertrag protokolliert. |
| F10 | Finanzielle Vertragsdaten | Gesamt-/Jahreswert in EUR, Richtung und ausdrückliche Netto-/Brutto-/unbekannte Wertbasis. Altdaten bleiben unbekannt; keine Steuerumrechnung, Zahlungs- oder Mittelbindungsrechnung. |
| F11 | § 2b UStG-Prüfung | Nur die Administration ändert die steuerliche Bewertung. Prüfstatus Noch nicht geprüft, Prüfung erforderlich, In Prüfung, Abgeschlossen oder Nicht relevant führen. Ergebnis oder Begründung dokumentieren; beim Abschluss speichert die Anwendung prüfende Person und Zeitpunkt. Die Anwendung erstellt keine rechtsverbindliche steuerliche Bewertung. |
| F12 | Prüf- und Freigabeprozess | Anfrage, Frist und Ergebnis dokumentieren; Administratoren weisen Vorgänge explizit einem Empfängerteam und berechtigten Konto zu. Zuweisungen erteilen keine zusätzlichen Vertragsleserechte. Entscheidungen sind seit Phase 4 an den Inhalt gebunden; seit Phase 5 sperren ungeprüfte aktuelle Dokumente die Freigabe. Eine persönliche Prüfliste zeigt entscheidbare Vorgänge. Es werden keine externen Nachrichten versendet. |
| F13 | Excel-Import und -Export | Alle passenden Verträge bis 5000 als literal-sichere XLSX exportieren, unabhängig von der Ergebnisseite. Import nur als Neuanlage bis 500 Zeilen, atomar bei Fehlern. Generierte Vertragsnummern müssen leer sein; optionale externe Referenzen sind fachbereichsbezogen eindeutig. Gleiche Beschreibungen sind zulässig und werden als mehrdeutig markiert. Kein Dokument-/Historienbackup oder automatischer Aktualisierungsmodus. |
| F14 | Auswertungen und Berichte | Erfasste Vertragswerte mit Richtung/Wertbasis und Fehlwertzählung. Historie aus protokollierten Vertragsständen, einschließlich heute archivierter/übertragener Verträge, mit damaligem Fachbereich. Unbekannte Richtungen werden nicht als Ausgabe gezählt. Ohne historische Belege keine erfundenen Nullwerte; aktuelle Jahrbeobachtung nur bis jetzt. D08 fachlich offen. |
| F15 | Schnittstellen | Versionierte, schreibgeschützte JSON-API für Verträge, Fachbereiche und Vertragsdokumente. Administratoren erstellen, begrenzen, befristen und widerrufen API-Tokens. |

### Vertragsstatus

Ein Vertrag hat einen fachlichen Status: **Entwurf**, **In Abstimmung**, **Aktiv**, **Gekündigt** oder **Beendet/abgelaufen**. Archivierung ist ein eigener Zustand; archivierte Verträge bleiben erhalten und werden als „Archiviert“ angezeigt.

### Benachrichtigungen

Erfolgs- und Fehlhinweise bleiben sichtbar. Erfolgsmeldungen können ausdrücklich geschlossen werden; Fehler verschwinden nicht automatisch. Zugewiesene offene Aufgaben und aktuelle entscheidbare Prüfungen mit Überfälligkeit stehen unter „Mein Arbeitskorb“. Hintergrundversand per E-Mail oder Push ist nicht eingerichtet.

## Bedienung

Nach der Anmeldung führt die Vertragsübersicht zu den Vertragslisten, Fristen, Suche und Schnellfiltern. Ein Vertrag lässt sich aus der Liste öffnen. Die Detailansicht enthält Vertragsdaten, Fristenberechnung, §-2b-Prüfung, Aufgaben, Prüf- und Freigabevorgänge, Unterlagen und Änderungshistorie. Administratoren sehen zusätzlich Benutzerverwaltung und Schnittstellenverwaltung.

Fachbereichsnutzer sind auf ihren zugewiesenen Fachbereich beschränkt. Prüfer können alle Verträge ansehen. Administratoren können Benutzer, Fachbereiche und Schnittstellen-Tokens verwalten. Berechtigungen für einzelne Verträge innerhalb eines Fachbereichs gibt es nicht.

## Schnittstellen-API F15

API-Tokens werden unter `/admin/integrations` durch Administratoren verwaltet. Ein Token kann auf einen Fachbereich begrenzt, auf 90 Tage oder ein Jahr befristet oder ohne Ablaufdatum angelegt werden. Der vollständige Token wird nur beim Erstellen angezeigt. Er kann jederzeit widerrufen werden; gespeichert wird nur sein Hash.

Für v2 sind ein verantwortliches Konto, ein benannter Dienst und ein endliches Ablaufdatum erforderlich. Rechte für Finanzen, Dokumentmetadaten/-inhalt, Steuerprüfung, Aufgaben und sensible Historie werden einzeln vergeben. Rotation stellt ein neues Geheimnis einmalig bereit; nach eigener Anfangssynchronisierung wird der Vorgänger ausdrücklich widerrufen. Der bisherige breite v1-Umfang bleibt ein separates Profil.

Neue Verbraucher verwenden `/api/v2/snapshot` und anschließend `/api/v2/changes`. Cursor sind undurchsichtige, an Token und Berechtigungen gebundene Werte. 410 verlangt einen neuen Anfangsbestand; bei 401/403 darf der Verbraucher seine alten Zugriffsrechte nicht weiter voraussetzen. [Vollständiger API-Vertrag](docs/PHASE6_INTEGRATION_SYNC.md), [Antwortschema](app/static/api-v2.schema.json). v1-Zeitfilter/Offsets ersetzen diesen Änderungsfeed nicht.

Alle API-Anfragen verwenden den Header `Authorization: Bearer <Token>`.

| Methode und Pfad | Zweck |
|---|---|
| `GET /api/v1/departments` | Fachbereiche abrufen |
| `GET /api/v1/contracts` | Vertragsdaten und Dokumentenverweise abrufen |
| `GET /api/v1/contracts/{contract_id}/documents/{document_id}` | Eine hochgeladene Vertragsdatei geschützt herunterladen |

Der Vertragsabruf unterstützt `limit` (1 bis 500), `offset` und `updated_since` als ISO-8601-Zeitpunkt, zum Beispiel `?updated_since=2026-10-20T00:00:00Z`. Die Antwort enthält `total` und `next_offset`. Archivierte Verträge werden mit `archived_at` geliefert. Dokumente enthalten entweder eine DMS-Adresse (`external_url`) oder eine geschützte Download-Adresse (`download_url`).

Beispiel:

```powershell
curl.exe -H "Authorization: Bearer <TOKEN>" `
  "http://127.0.0.1:8000/api/v1/contracts?limit=100&offset=0"
```

Die API liest Daten aus dem Register; sie legt keine Verträge an und ändert keine Datensätze. Eine direkte Synchronisierung mit H&H, LDAP oder einem konkreten DMS ist nicht enthalten. Dafür werden die Schnittstellendokumentation, der Importweg und die technischen Zugangsdaten des Zielsystems benötigt.

## Lokal starten – Windows PowerShell

Öffne PowerShell im **Projektordner**, also `C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase`. Die Befehle funktionieren nicht aus dem übergeordneten Ordner `C:\kämmerei`, weil dort das Python-Paket `app` nicht liegt.

Falls noch keine virtuelle Python-Umgebung im Projektordner existiert:

```powershell
py -m venv .venv
```

Abhängigkeiten installieren und Datenbank auf den aktuellen Stand bringen:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.cli init-db
```

Für eine neue Datenbank Fachbereiche und den ersten Administrator anlegen. `add-user` fragt interaktiv nach einem Passwort (12 bis 256 Zeichen). Diese Befehle nur für noch nicht vorhandene Einträge ausführen:

```powershell
.\.venv\Scripts\python.exe -m app.cli add-department "Kämmerei"
.\.venv\Scripts\python.exe -m app.cli add-user admin --role admin
```

Anwendung starten:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Im Browser öffnen: [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login). Es gibt keine voreingestellten Benutzerkonten oder Passwörter. Zum Beenden des Servers im PowerShell-Fenster `Ctrl+C` drücken.

Die Datenbankdatei liegt standardmäßig unter `data/vertragsregister.sqlite3`; hochgeladene Dokumente werden standardmäßig unter `data/documents/` gespeichert. Mit `DATABASE_URL` und `DOCUMENT_STORAGE_DIR` können diese Pfade angepasst werden. `APP_ENV` und `ALLOWED_HOSTS` konfigurieren die Laufzeitumgebung und erlaubten Hostnamen.

## Administration über die Kommandozeile

Die Befehle im Projektordner mit derselben Python-Umgebung ausführen:

```powershell
.\.venv\Scripts\python.exe -m app.cli list-departments
.\.venv\Scripts\python.exe -m app.cli add-department "Kultur"
.\.venv\Scripts\python.exe -m app.cli add-user kultur --role department --department "Kultur"
.\.venv\Scripts\python.exe -m app.cli add-user pruefung --role reviewer
.\.venv\Scripts\python.exe -m app.cli change-password admin
.\.venv\Scripts\python.exe -m app.cli disable-user kultur
.\.venv\Scripts\python.exe -m app.cli purge-sessions
```

`init-db` wendet versionierte Alembic-Migrationen an. Vor Migrationen einer vorhandenen Datenbank eine Sicherung anlegen. Aktueller Kopf: `0023_human_mfa`; eine vorhandene Geschäftsdatenbank wurde hier nicht migriert. `schema-inventory` liefert ausschließlich Strukturabweichungen und IDs ungültiger Datensätze. Frühere optionale Fachbereichszuordnungen von Administrator-/Prüferkonten stoppen Migration 0015 und benötigen eine ausdrücklich geprüfte Korrektur. Fachbereichskonten benötigen einen aktiven Fachbereich. Start-/Wiederherstellungspasswörter müssen nach der Anmeldung unter „Passwort ändern“ ersetzt werden. Bei aktivierter Datenbanksicherheit verwenden CLI/Alembic ausschließlich den expliziten Betreiberzugang `MIGRATION_DATABASE_URL`; `purge-sessions` verwendet `MAINTENANCE_DATABASE_URL` und die eng begrenzte Wartungsfunktion. Einrichtung und Grenzen stehen im Phase-3-Bericht.

## Dokumente und Daten

- Pro Upload können bis zu fünf Dateien ausgewählt werden; jede Datei darf höchstens 25 MB groß sein.
- Unterstützte Dateitypen sind PDF, Office- und OpenDocument-Dateien, RTF, TXT, CSV sowie PNG, JPEG und GIF.
- PDF- und Bilddateien können in der Anwendung angezeigt werden; andere Formate können heruntergeladen werden.
- Dokumente liegen im konfigurierten Dokumentenspeicher. Ein Datenbank-Backup allein sichert diese Dateien nicht.
- DMS-Verknüpfungen speichern einen externen HTTP(S)-Link und einen Anzeigenamen; die Datei bleibt im DMS.
- Excel-Importe sind auf 500 Vertragszeilen begrenzt.

## Tests und Entwicklung

Entwicklungsabhängigkeiten und Tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Die Tests nutzen eine isolierte temporäre SQLite-Datenbank mit synthetischen Daten und verändern keine regulären Vertragsdaten.

Die Phase-1-Prüfbasis ist zusätzlich ohne pytest über die Python-Standardbibliothek ausführbar (httpx und die Laufzeitabhängigkeiten werden weiterhin benötigt):

```powershell
.\.venv\Scripts\python.exe scripts\verify_phase1.py --database sqlite
# Getrennte native Testinstanz starten; bestehende Windows-Dienste bleiben unberührt:
& .\scripts\Start-TestDatabase.ps1 -Python '.\.venv\Scripts\python.exe'
.\.venv\Scripts\python.exe scripts\verify_phase1.py --database postgresql
# Nur die eigene Testinstanz stoppen; Daten bleiben erhalten:
& .\scripts\Stop-NativeTestDatabase.ps1 -Python '.\.venv\Scripts\python.exe'
```

Im gegenwärtigen Arbeitsverzeichnis ist die getestete Python-Umgebung `C:\kämmerei\.venv\Scripts\python.exe`; die projektlokale Umgebung ist noch nicht eingerichtet. Für eine Neuinstallation gelten die Installationsschritte oben. Ergebnisse und Gründe für nicht ausgeführte Prüfungen stehen im Phase-1-Nachweis. Erwartete Fehler zählen weiterhin als offene Befunde. Der Prüflauf aktualisiert `.verification/phase1-<Datenbank>.json`; dort gespeicherte Daten sind synthetisch und gehören nicht in eine Veröffentlichung.

Für einen ausdrücklich bereitgestellten lokalen Testcluster lässt sich alternativ `TEST_POSTGRES_ADMIN_URL` setzen und `scripts\verify_phase1.py --database postgresql` beziehungsweise `pytest --database postgresql` ausführen. Die Adresse muss auf die Verwaltungsdatenbank `postgres` zeigen; jede Prüfung legt eine neue Datenbank mit zufälligem Namen an. Niemals hierfür einen produktiven Cluster verwenden. Die CI-Definition führt diese Abläufe getrennt für SQLite und PostgreSQL aus; der erfolgreiche Lauf ist im [Nachweis](docs/evidence/phase1-ci-39571113046.json) dokumentiert. `scripts\Complete-Phase1Setup.ps1` richtet standardmäßig die native Testinstanz ein und unterstützt optionalen Push; Docker bleibt über `-DatabaseBackend Docker` wählbar. Siehe [Einrichtung](docs/VERIFICATION_SETUP.md).

Die Anwendung verwendet FastAPI, SQLAlchemy, Alembic, Jinja2 und SQLite in der lokalen Standardkonfiguration. Die Weboberfläche ist serverseitig gerendert und verwendet keine externen CDNs.

## Betrieb und Sicherheitsgrenzen

Die lokale Konfiguration bindet an `127.0.0.1` und ist nur auf diesem Rechner erreichbar. Für einen internen Server sind unter anderem eine abgesicherte HTTPS-Verbindung, Reverse Proxy, PostgreSQL, Backups mit Restore-Test, Zugriffs- und Aufbewahrungskonzept sowie die Konfiguration von `APP_ENV=production`, `DATABASE_URL` und `ALLOWED_HOSTS` erforderlich. In Produktion werden sichere Session-Cookies und HSTS gesetzt; die Anwendung weist SQLite und unsichere Host-Konfigurationen zurück.

Vor einem dienstlichen Produktivbetrieb sind fachliche Abnahme, Datenschutzprüfung, Sicherheitsprüfung und Freigabe durch die zuständigen Stellen erforderlich. Insbesondere stellen der §-2b-Prüfstatus und die Prüfabläufe keine rechtsverbindliche steuerliche oder rechtliche Entscheidung dar.

## Projektdateien

- `app/main.py`: Webrouten und HTTP-API
- `app/models.py`: Datenbankmodelle
- `app/logic.py`: Validierung, Berechtigungen und Vertrags-Snapshots
- `app/security.py`: Anmeldung, Sitzungen, CSRF und Anmeldebegrenzung
- `app/cli.py`: Administration und Datenbankmigrationen
- `app/templates/`, `app/static/`: Weboberfläche und Gestaltung
- `alembic/versions/`: versionierte Datenbankmigrationen
- `tests/`: automatisierte Tests
- `docs/ARBEITSPLAN.md`: Umsetzungsstand, offene fachliche Fragen und nächste Schritte

Phase 9 U018 continues with durable scan batches, review-only native Windows operations templates, approved workload/recovery targets and statement-scoped RLS/read optimizations (head 0022). Initial workload failures are preserved in docs/evidence/phase9-workload-before.json. Full current-source verification and remaining MFA/backup/deployment gates are tracked in HANDOFF.md and docs/PHASE9_OPERATIONS.md. No Phase 9 exit or deployment acceptance.

Phase 9 U019 implements the approved local TOTP strategy: encrypted user-bound seeds, operator-authorized enrollment/recovery, short pending challenges, persisted replay protection, PostgreSQL enforcement and separate service credentials. Head 0023; full SQLite 244 collected: 219 passed + 25 explicit skips, 15 passing subtests. Full PostgreSQL and exact-source hosted verification are running; no production rollout or Phase 9 exit. See HANDOFF U019 and docs/PHASE9_OPERATIONS.md.

U019 final checkpoint ece7797: 244 collected; native PostgreSQL 242 passed/2 local skips; SQLite 219 passed/25 explicit skips; 15 passing subtests each; explicit PostgreSQL 23 passed. All five exact-source hosted jobs passed (39656369586). TOTP implementation technically verified; production custody/deployment and the remaining Phase 9 gates remain open. Evidence in HANDOFF U019 and docs/evidence/phase9-u019-local.json.


Phase 9 U020 adds owner-operated encrypted/signed PostgreSQL plus private-file
backup and verified restore-bundle commands, with a disabled native Windows task
draft. No production task, key escrow or deployment activated. Local development
needs no municipal approval; proposed IT operating/recovery roles are provisional
for future production only. Targeted 29 tests passed; current full/hosted results
are tracked in HANDOFF. Phase 9 remains open. See docs/PHASE9_OPERATIONS.md.


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


Phase 10 preparation: [acceptance worksheet](docs/PHASE10_ACCEPTANCE.md) maps
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
