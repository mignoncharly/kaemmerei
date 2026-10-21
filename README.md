# OPEN.HERZ Vertragsregister

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

Offen bleiben unter anderem historische Finanzsummen und die fachlichen Datums-/Excel-Regeln der Phase 7. R01/R04/R10 bleiben durch reguläre Tests abgesichert. Eine fachliche oder betriebliche Produktivfreigabe ist damit nicht verbunden.

Aktueller Zustand und jede Arbeitsänderung stehen in [HANDOFF.md](HANDOFF.md). [Prüfmatrix](docs/VERIFICATION_MATRIX.md) und [Phase-1-Nachweis](docs/PHASE1_BASELINE.md) trennen bestandene Prüfungen, bekannte Fehler und noch nicht ausgeführte Prüfungen. H&H-/LDAP-/produktspezifische DMS-Anbindungen und externe Erinnerungen bleiben ausdrücklich außerhalb des bisher gelieferten Umfangs.

## Funktionsübersicht

| Nr. | Funktion | Was die Anwendung bietet |
|---|---|---|
| F1 | Zentrale Vertragsverwaltung | Verträge anlegen, suchen, filtern, bearbeiten und archivieren. Jeder Vertrag erhält eine automatisch erzeugte Vertragsnummer. Änderungen verwenden Versionsschutz, damit eine ältere Bearbeitung keine neueren Daten überschreibt. |
| F2 | Vertragsdokumente | PDF- und weitere Vertragsdateien hochladen, speichern, herunterladen und – bei PDF oder Bilddateien – in einer Vorschau öffnen. Alternativ lässt sich ein Dokument im vorhandenen Dokumentenmanagementsystem verknüpfen. Dateien können schon beim Erstellen eines Vertrags hinzugefügt werden. |
| F3 | Fachbereichsverwaltung | Administratoren pflegen Fachbereiche, Kontakte und Empfängerteams unter „Fachbereiche & Identitäten“. Umbenennen, Deaktivieren und Reaktivieren erhalten stabile IDs und historische Anzeigenamen. Kontakte sind fachbereichsbezogen oder bewusst global geteilt. Kontakt- und Vertretungsbezeichnungen erteilen keine Zugriffsrechte. |
| F4 | Benutzer und Berechtigungen | Administratoren verwalten Konten und explizite Freigabefähigkeit. Fachbereichsnutzer bearbeiten ihren aktiven Fachbereich. Prüfer lesen alle Verträge; Entscheidungen erfordern zusätzlich aktive Teammitgliedschaft und konkrete Zuweisung. Passwortwechsel und administrative Wiederherstellung widerrufen Sitzungen; Start-/Wiederherstellungspasswörter müssen ersetzt werden. |
| F5 | Vertragsfristen | Vertragsbeginn, Vertragsende, Kündigungsfrist und automatische Verlängerung mit Verlängerungszeitraum erfassen. Kündigungsstichtage und nächste Verlängerungstermine werden berechnet. |
| F6 | Erinnerungen und Warnungen | Überfällige und innerhalb der nächsten 90 Tage anstehende Vertragsfristen erscheinen in der Übersicht; überfällige Aufgaben werden hervorgehoben. Es gibt keine E-Mail- oder Push-Erinnerungen. |
| F7 | Dashboard und Suche | Kennzahlen und Schnellfilter für aktive, bald auslaufende, ungeprüfte, zur Freigabe eingereichte sowie gekündigte oder beendete Verträge. Such- und Listenfilter umfassen Bezeichnung, Vertragsnummer, Vertragspartner, Fachbereich, Vertragsart, zuständige Person, Vertretung, Vertragsstatus und §-2b-Prüfstatus. Archivierte Verträge lassen sich über den Vertragsstatus anzeigen. |
| F8 | Bearbeitungsstatus und Aufgaben | Je Vertrag Aufgaben für Prüfung, Vervollständigung, Aktualisierung oder sonstige Arbeiten erfassen. Aufgaben haben Titel, Beschreibung, Fälligkeit, zuständige Person und Status Offen, In Bearbeitung oder Erledigt. |
| F9 | Änderungshistorie | Vertragsänderungen mit handelndem Benutzer, Zeitpunkt und verständlich dargestellten geänderten Feldern nachvollziehen. Erstellen, Bearbeiten, Archivieren, Dokumente, Aufgaben und Prüfabläufe werden am jeweiligen Vertrag protokolliert. |
| F10 | Finanzielle Vertragsdaten | Gesamtvertragswert, Jahreswert, Einnahme oder Ausgabe, Zahlungsintervall und Haushaltszuordnung beziehungsweise Produktkonto erfassen. |
| F11 | § 2b UStG-Prüfung | Prüfstatus Noch nicht geprüft, Prüfung erforderlich, In Prüfung, Abgeschlossen oder Nicht relevant führen. Ergebnis oder Begründung dokumentieren; beim Abschluss speichert die Anwendung prüfende Person und Zeitpunkt. Die Anwendung erstellt keine rechtsverbindliche steuerliche Bewertung. |
| F12 | Prüf- und Freigabeprozess | Anfrage, Frist und Ergebnis dokumentieren; Administratoren weisen Vorgänge explizit einem Empfängerteam und berechtigten Konto zu. Zuweisungen erteilen keine zusätzlichen Vertragsleserechte. Entscheidungen sind seit Phase 4 an den Inhalt gebunden; seit Phase 5 sperren ungeprüfte aktuelle Dokumente die Freigabe. Eine persönliche Prüfliste zeigt entscheidbare Vorgänge. Es werden keine externen Nachrichten versendet. |
| F13 | Excel-Import und -Export | Gefilterte Vertragslisten als `.xlsx` exportieren. Eine Importvorlage herunterladen und bis zu 500 Verträge je Import übernehmen. Importdaten werden geprüft; bei Fehlern wird der Import nicht teilweise ausgeführt. Dubletten werden erkannt. |
| F14 | Auswertungen und Berichte | Jahresausgaben und -einnahmen, Vertragswerte, Aufgaben, Prüfungen und Fristen nach Fachbereich vergleichen. Die Finanzentwicklung zeigt bis zu fünf Jahre anhand protokollierter Änderungen. Die aktuelle Rekonstruktion berücksichtigt nur heute nicht archivierte Verträge; Archivierung oder Fachbereichswechsel kann historische Zahlen verändern. Korrektur und fachliche Definition sind für Phase 7 vorgesehen. |
| F15 | Schnittstellen | Versionierte, schreibgeschützte JSON-API für Verträge, Fachbereiche und Vertragsdokumente. Administratoren erstellen, begrenzen, befristen und widerrufen API-Tokens. |

### Vertragsstatus

Ein Vertrag hat einen fachlichen Status: **Entwurf**, **In Abstimmung**, **Aktiv**, **Gekündigt** oder **Beendet/abgelaufen**. Archivierung ist ein eigener Zustand; archivierte Verträge bleiben erhalten und werden als „Archiviert“ angezeigt.

### Benachrichtigungen

Erfolgs- und Fehlhinweise in der Weboberfläche verschwinden nach fünf Sekunden. Die Fristen- und Aufgabenhinweise werden in den Übersichten angezeigt. Hintergrundversand per E-Mail oder Push ist nicht eingerichtet.

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

`init-db` wendet versionierte Alembic-Migrationen an. Vor Migrationen einer vorhandenen Datenbank eine Sicherung anlegen. Aktueller Kopf: `0017_bound_workflow`; eine vorhandene Geschäftsdatenbank wurde hier nicht migriert. `schema-inventory` liefert ausschließlich Strukturabweichungen und IDs ungültiger Datensätze. Frühere optionale Fachbereichszuordnungen von Administrator-/Prüferkonten stoppen Migration 0015 und benötigen eine ausdrücklich geprüfte Korrektur. Fachbereichskonten benötigen einen aktiven Fachbereich. Start-/Wiederherstellungspasswörter müssen nach der Anmeldung unter „Passwort ändern“ ersetzt werden. Bei aktivierter Datenbanksicherheit verwenden CLI/Alembic ausschließlich den expliziten Betreiberzugang `MIGRATION_DATABASE_URL`; `purge-sessions` verwendet `MAINTENANCE_DATABASE_URL` und die eng begrenzte Wartungsfunktion. Einrichtung und Grenzen stehen im Phase-3-Bericht.

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
