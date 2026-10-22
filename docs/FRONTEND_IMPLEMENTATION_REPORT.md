# OPEN.HERZ Vertragsregister – Frontend-Redesign

Ergänzung: [Excel-Auswahl-Export und Importführung](EXCEL_SELECTION_IMPLEMENTATION.md)
mit serverseitiger Prüfung, Regressionsergebnissen und offener Browserabnahme.

Aktuelle Layoutkorrektur: [„Suche & Filter“ als Popover / Drawer](CONTRACT_FILTER_POPOVER_IMPLEMENTATION.md).
Die permanente Suchleiste entfällt; Kennzahlen und Tabellenkopf sind kompakt.

Nachtrag zur Vertragsübersicht: [Kompakte Toolbar und Filter](CONTRACT_TOOLBAR_IMPLEMENTATION.md)
dokumentiert die gezielte Weiterentwicklung einschließlich eigener Regression
und noch ausstehender Browserabnahme. Die nachfolgenden Ergebnisse beziehen
sich auf den ursprünglichen Gesamtredesign-Stand.

Stand: 22.10.2026. **Implementierung und lokale funktionale Regression sind
abgeschlossen; die visuelle und interaktive Browserabnahme ist umgebungsbedingt
offen. Das Gesamtvorhaben ist damit noch nicht vollständig abgenommen.**

## Ergebnis und Arbeitsstand

Separater Worktree: `C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign`.
Branch: `redesign/frontend-dashboard`. Ausgangsrelease: `3d4a180`.
Konservierter lokaler Ausgangsstand einschließlich der vorhandenen Vorarbeiten:
`6437141`. Implementierung: `fb55d0c`.

Die 30 geänderten oder unversionierten Originaldateien wurden zuerst in den
Worktree kopiert. Ihre Git-normalisierten Inhalts-Hashes wurden anschließend
gegen diesen Ausgangsstand geprüft: **30 von 30 unverändert**. Das ursprüngliche
Arbeitsverzeichnis bleibt auf `review/u026-synthetic-pilot`. U026-CI-Evidenz,
STRATO-Unterlagen und `Start-TestDatabase.ps1` wurden nicht überarbeitet.
Es gab keinen Push, Merge, Deployment oder STRATO-Zugriff.

## Umgesetzte Oberfläche

- Gemeinsame 248-px-Sidebar, gruppierte Navigation, aktueller Menüpunkt,
  Breadcrumb, Kontomenü und Abmeldung mit bestehendem CSRF-Schutz.
- Separater Überblick `/dashboard`; die bestehende Anmelde-Zieladresse
  `/?notice=login` zeigt diesen Überblick ebenfalls. `/` bleibt Vertragsbestand.
- Reale, bereits autorisierte Kennzahlen und Fristen; höchstens sechs Datensätze
  in der Übersicht. Keine synthetischen Kennzahlen in Anwendungstemplates.
- Vertragsbestand mit serverseitiger Suche, Filtern, begrenzter Pagination,
  Export, zugänglichem Importbereich und erhaltenem Zugang zu allen Fristen.
- Vertragsdetails mit Abschnittsnavigation, gruppierten Stammdaten,
  Zuständigkeiten, Laufzeit, Finanzangaben, Aufgaben, Prüfungen, Unterlagen,
  Entscheidungs- und Änderungshistorie sowie Archivierungsbestätigung.
- Vertragsformulare mit fünf beschrifteten Feldgruppen. Bestehende Werte,
  CSRF-, Request-ID- und Versionsfelder bleiben erhalten.
- Benutzerverwaltung, Benutzerformulare, Fachbereiche, Kontakte, Teams,
  Mitgliedschaften und Integrationsverwaltung im gleichen Komponentensystem.
- Persönlicher Arbeitskorb berücksichtigt weiterhin aktuelle Revision,
  konkrete Zuweisung, Freigabefähigkeit und bestehenden Vertragszugriff.
- Eigenständiges Layout für Login, MFA und erzwungenen Passwortwechsel.
  Normale Kontoeinstellungen verwenden die Anwendungshülle.
- Gestaltete Import-, Validierungs-, Zugriffs-, Nichtgefunden-, Konflikt- und
  Serverfehlerzustände. Unerwartete Fehler zeigen keine Exception-Texte.
- Dokumentstatus verständlich beschriftet; Downloads nur für verfügbare,
  sauber geprüfte Dateien mit Prüfsumme. DMS- und Archivschutz bleiben bestehen.
- Rückmeldungen nach bestätigten Verwaltungs-, Passwort-, Zuweisungs- und
  Dokumentaktionen. Integrationsformulare bewahren nicht geheime Eingaben bei
  Fehlern. Passwörter, Tokens und Dateien werden nicht wieder eingeblendet.

Die Abfragen, Datenmodelle, Migrationen, Rechteprüfung, MFA-Regeln, Archivlogik,
Scanner und Produktionskonfiguration wurden nicht durch ein neues Frontend-
System ersetzt. Kleine Backend-Anpassungen betreffen Rendering-Auswahl,
sichere Fehlernavigation, Darstellungswerte und Rückmeldungen nach bestehenden
Transaktionen. API-Antworten bleiben maschinenlesbar.

## Vollständigkeit und Design

[Routenmatrix](FRONTEND_ROUTE_MATRIX.md): 55 tatsächliche GET-/POST-Routen,
einschließlich API, Downloads und Health. [Ausgangsbestand und Zustände](FRONTEND_REDESIGN_PROGRESS.md)
ordnet alle 16 ursprünglichen Templates, Aktionen, Zustände und Testziele zu.
Zusätzlich entstanden Dashboard, Komponenten-Makros und zwei gemeinsame Partials.
Alle ursprünglichen Seitentemplates wurden bearbeitet.

API, Health, XLSX und Dokumentdownloads bekommen keine künstlichen HTML-Seiten.
Es existiert weiterhin keine globale Dokumentensuche, Benachrichtigungszentrale,
eigenständige Rollenverwaltung oder erfundene Administration-Startseite.
Dokumente und Prüfaktionen bleiben im jeweiligen Vertragskontext.

[Designsystem](FRONTEND_DESIGN_SYSTEM.md): Navy, Weiß/Hellgrau und Petrol;
Systemschrift, zentrale Tokens und Komponenten, lokale SVG-Icons. Keine neue
Frontend-Runtime oder externe Assets. CSS ca. 34 KB, Interaktionsskript ca. 4,5 KB.

## Ausgeführte Verifikation

| Prüfung | Ergebnis |
|---|---|
| Baseline `test_phase8.py`, `test_app.py` | 19 bestanden |
| Vollständige Pytest-Suite, SQLite | **416 bestanden, 44 übersprungen**, 15 Subtests bestanden; 149,15 s |
| Abschließende betroffene Formular-/Identitäts-/UI-Tests | 37 bestanden |
| Laufender Uvicorn-Prozess, echte HTTP-Anfragen | 33 Seiten-/Rollenprüfungen bestanden |
| Gerendertes HTML | Verschachtelung, eindeutige IDs, Beschriftungen, Shell, Rechte und CSP geprüft |
| Python-Kompilierung / JS-Syntax | bestanden |
| `git diff --check` | bestanden |
| Zwölf definierte Kontrastpaare | bestanden; Text mindestens 4,97:1, Eingaberand 3,23:1 |
| Browserautomation | **blockiert**, kein Browser gestartet |
| Screenshots und visuelle Inspektion | **nicht durchgeführt**, keine Screenshots geliefert |
| Tastatur, Drawer, Zoom, Screenreader im Browser | **nicht durchgeführt** |
| PostgreSQL-Lauf | **blockiert**, kein neuer Testcluster gestartet |
| Lastziel 10 Nutzer / 10.000 Verträge / 50.000 Dokumente | **nicht erneut gemessen** |

Der erste Gesamtlauf fand zwei fehlende Fristen-Verweise. Diese wurden durch den
gemeinsamen Fristenbereich wiederhergestellt. Der zusätzliche HTML-Test fand
eine doppelte Dokument-ID; Abschnitt und Dateifeld haben jetzt unterschiedliche
IDs. Die betroffenen Tests wurden erfolgreich wiederholt. Es wurden keine
bestehenden Tests abgeschwächt oder auf fehlerhaftes Verhalten angepasst.

Die 44 Skips betreffen tatsächliche PostgreSQL-/RLS-/Parallelitätsprüfungen,
native `age`-Verschlüsselung, echten ClamAV und die unter Windows nicht erlaubte
Symlink-Erzeugung. Die vollständige Zuordnung jedes Skips steht in
[sanitisierter Evidenz](evidence/frontend-redesign.json). Eine bestehende
FastAPI/Starlette-TestClient-Deprecation-Warnung bleibt unverändert.

Lokale Rohprotokolle: `.verification/final-tests.txt`, `final-tests.xml`,
`changed-workflows.txt`, `live-http.json`, `contrast.json` und
`redesign-browser-final/result.json`. Diese Dateien enthalten synthetische
Prüfungen; sie ersetzen keine produktive Abnahme.

## Konkrete Umgebungsblockaden

Der vorhandene U026-Browserprüfer und der neue erweiterte Prüfer enden mit
`automation_driver_permission_denied`, `PermissionError`, `WinError 5`, bevor
Playwright einen Browser startet. Ein zusätzlicher Node/Edge-Start meldete
`spawn EPERM`. Der Browser-Connector meldete keine verfügbare Browserinstanz.
Es gibt deshalb weder Browser-Pass noch geprüfte Screenshots.

Der unveränderte PostgreSQL-Testcluster-Launcher konnte die erforderlichen
owner-only-Dateiberechtigungen nicht setzen. Er meldete ausdrücklich, dass
keine neuen Zugangsdaten geschrieben und keine vorhandenen PostgreSQL-Dienste
geändert wurden. Produktive Schutzmaßnahmen wurden nicht gelockert.

## Lokal unter Windows starten

In diesem Arbeitsplatz sind die Python-Abhängigkeiten vorhanden:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
python scripts\preview_frontend.py --port 8766
```

Im Browser `http://localhost:8766` öffnen. Synthetische Konten:
`admin`, `kultur`, `bau`, `pruefer`. Gemeinsames **reines Testpasswort**:
`NurZumTesten-Starkes-Passwort-2026`.

Die Vorschau bindet ausschließlich Loopback, verwendet eine neu erzeugte,
migrierte SQLite-Datenbank und den vorhandenen synthetischen Testscanner. Sie
benutzt keine Geschäftsdaten. Mit `Ctrl+C` beenden; die temporären Daten werden
bereinigt. Für eine leere Pilotansicht stattdessen:

```powershell
python scripts\preview_frontend.py --port 8766 --empty
```

Nur falls eine neue Python-Umgebung benötigt wird:

```powershell
python -m venv .venv-test
.\.venv-test\Scripts\python.exe -m pip install -r requirements-browser.txt
.\.venv-test\Scripts\python.exe scripts\preview_frontend.py --port 8766
```

Das Vorschauprogramm ist ausschließlich ein Testwerkzeug; es ersetzt keine
Produktionsinstallation, MFA-Provisionierung oder echten Virenscanner.

## Ausstehende Browserabnahme ausführen

In einer normalen, für Browserprozesse autorisierten lokalen PowerShell mit
installiertem Edge, nach Beenden der Vorschau bei Bedarf:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
$runName = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts\verify_frontend_redesign.py --channel msedge --output ".verification\browser-$runName"
```

Der Prüfer verlangt einen committeten Quellstand. Er startet ausschließlich eine
eigene synthetische Anwendung und integriert die unveränderten U026-Journeys:
Erstellen, Bearbeiten, Validierungsfehler, Upload/Download, Fachbereichsisolation,
Archivierung und MFA samt Replay-Schutz. Die Erweiterung erfasst alle Rollen,
Verwaltungsseiten, tatsächliche Prüferaktionen, Konflikte, leeren Bestand,
Dokument-Prüfstände, Login/MFA und Fehlerseiten.

Breiten: 320, 390, 768, 1280 und 1440 px. Überlauf, Hauptüberschrift,
Navigationsrechte, Drawer-Fokus, Escape und CSP werden geprüft. PNGs entstehen
aus dem laufenden Browser; der MFA-Schlüssel wird für den Screenshot maskiert.
Geheimnisse oder vollständige Anwendungsantworten gehören nicht ins Prüfprotokoll.

Anschließend alle erzeugten PNGs tatsächlich öffnen und auf Ausrichtung,
Lesbarkeit, Tabellen, Formularabstände und abgeschnittene Controls prüfen.
Zusätzlich 200-%-Zoom, vollständige Tastaturwege und einen Screenreader prüfen.
Erst danach eine separate visuelle Prüfliste mit Dateinamen, Viewport, Befund und
Korrektur dokumentieren. Der Browserprüfer setzt `visual_inspection` bewusst
weiterhin auf `NOT_PERFORMED`; Screenshot-Erzeugung ist keine visuelle Abnahme.

## PostgreSQL und übrige Gates nachholen

Der bereits vorhandene autorisierte Testworkflow kann in einer normalen lokalen
PowerShell einen gesonderten Testcluster auf Port 55436 vorbereiten:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
.\scripts\Start-TestDatabase.ps1 -Backend Native -Port 55436
python -m pytest -q -ra --database postgresql -p no:cacheprovider
```

Die vorhandenen Fixtures prüfen Loopback, dedizierte Rollen und isolierte
Datenbanken. Keine Geschäftsdatenbank als Ersatz verwenden. ClamAV, native
`age`-Werkzeuge und die bestehende Lastmessung müssen mit den bereits vorgesehenen
U026-Prüfvoraussetzungen nachgewiesen werden. Alte Hosted-CI-Ergebnisse bleiben
Release-Evidenz des alten Stands und sind kein Testlauf dieses Redesigns.

## Exakte geänderte Dateien

Vergleich ausschließlich gegen den konservierten lokalen Ausgangsstand
`6437141`, nicht gegen das unveränderte ursprüngliche Arbeitsverzeichnis:

```text
app/document_routes.py
app/identity_routes.py
app/main.py
app/presentation.py
app/static/interface.js
app/static/site.css
app/templates/base.html
app/templates/components.html
app/templates/dashboard.html
app/templates/detail.html
app/templates/error.html
app/templates/form.html
app/templates/identities.html
app/templates/import_result.html
app/templates/integrations.html
app/templates/list.html
app/templates/login.html
app/templates/mfa.html
app/templates/partials/metrics.html
app/templates/partials/reminders.html
app/templates/password.html
app/templates/reports.html
app/templates/review_inbox.html
app/templates/user_form.html
app/templates/users.html
app/templates/workflow_conflict.html
docs/FRONTEND_DESIGN_SYSTEM.md
docs/FRONTEND_IMPLEMENTATION_REPORT.md
docs/FRONTEND_REDESIGN_PROGRESS.md
docs/FRONTEND_ROUTE_MATRIX.md
docs/evidence/frontend-redesign.json
scripts/frontend_inventory.py
scripts/preview_frontend.py
scripts/verify_frontend_redesign.py
tests/test_frontend_redesign.py
```

Unversionierte `.verification`-Hilfsdateien sind lokale Arbeits-/Testartefakte.
Die ursprünglichen Dokumentations-, STRATO-, Formular-, Optionslisten- und
Teständerungen gehören zum konservierten Ausgangsstand und werden nicht als
Redesign-Leistung ausgewiesen.
