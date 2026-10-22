# Excel-Auswahl-Export und verständlicher Import

## Layoutkorrektur: ein gemeinsames Aktionsraster

Nachtrag vom 22.10.2026, Implementierung
`d250a03ac896df29dd3accdcc1bce2319271773b`:

- Vorlagenlink, Dateiauswahl und Importknopf liegen im selben dreispaltigen Grid
  mit einheitlich 48 px Höhe. Bis 700 px werden sie gleich breit gestapelt.
  Keine kompensierenden Abstände oder Transformationen für die Ausrichtung.
- Die native Dateiauswahl bleibt als vollständig beschriftetes, fokussierbares
  Dateifeld erhalten und liegt innerhalb einer gleich hohen Picker-Schaltfläche.
  Der Fokus wird am gesamten Bedienelement sichtbar markiert.
- Formathinweis, Dateiname und Fehler stehen außerhalb der drei Grid-Zellen
  unter der Aktionszeile. Die Erklärung ist eine kompakte nummerierte Schrittfolge.
- Mit JavaScript bleibt der Importknopf deaktiviert, bis eine nicht leere
  `.xlsx`-Datei bis einschließlich 10 MiB ausgewählt ist. Entfernen oder eine
  ungültige Auswahl deaktiviert ihn erneut. Diese lokale Vorprüfung bestätigt
  keine Arbeitsmappeninhalte; sämtliche Backendprüfungen bleiben unverändert.
  Ohne JavaScript bleibt ein nativer Submit-Fallback mit Pflicht-Dateifeld erhalten.
- Keine Backend-, Berechtigungs-, Export- oder sonstigen Seitenänderungen.

Geänderte Implementierungsdateien: `app/templates/list.html`,
`app/static/site.css`, `app/static/interface.js`,
`scripts/verify_excel_selection.py`; dazu dieser Bericht.

Verifikation: **31 Tests bestanden, keine Skips, 19,38 s**
(`test_excel_selection.py`, `test_frontend_redesign.py`), JS-Syntax,
Python-Kompilierung und `git diff --check` bestanden. Eine bestehende Starlette-
Deprecation-Warnung bleibt. Protokolle:
`.verification/import-grid-tests.txt` und `import-grid-tests.xml`.

Der aktualisierte Browserprüfer kontrolliert bei 390/768/1280/1440 px die
48-px-Höhen, gleiche obere Kanten auf Desktop/Tablet, gleiche Breiten und
vertikale Reihenfolge mobil, Dateifokus, deaktivierten Ausgangszustand,
falsche Endungen, leere/zu große Dateien, gültige Auswahl und erneutes Leeren.
Die Rollenprüfung und tatsächlichen Import-/Export-Journeys bleiben erhalten.

**Nicht ausgeführt:** Browsermessungen, Sichtprüfung und Screenshots.
Der synthetische Server startete; der Playwright-Treiber scheiterte erneut mit
`PermissionError / WinError 5`, bevor ein Browser gestartet wurde. Der Browser-
Connector meldete ebenfalls keine Instanz. Evidenz:
`.verification/import-grid-browser/result.json`, Quellstand wie oben,
`screenshots: []`, `visual_inspection: NOT_PERFORMED`.
Es wird keine gemessene pixelgenaue Ausrichtung behauptet.

Lokal in einer für Browserprozesse autorisierten PowerShell nachprüfen:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
$gridRun = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts\verify_excel_selection.py --channel msedge --output ".verification\import-grid-$gridRun"
```

Anschließend die tatsächlichen `{Rolle}-import-{Breite}.png`-Aufnahmen ansehen.
Die Nutzerreferenz `docs/korrekt.png` blieb ebenso wie die früheren Referenzbilder
unverändert und unversioniert. Kein Push, Merge oder Deployment.

---

Der folgende Bericht beschreibt die zuvor implementierte Export-/Importfunktion.

Stand: 22.10.2026. Worktree `OPEN_HERZ_Vertragsregister_Redesign`, Branch
`redesign/frontend-dashboard`. Implementierung:
`352b705cd3c0aa5cb07038876e1b7173556b29ae`.

**Implementiert und funktional geprüft. Browser-/Sichtprüfung ist blockiert
und bleibt offen.** Die vom Nutzer bereitgestellten PNGs sind Referenzen,
keine von der Anwendung erzeugten Abnahmescreenshots.

## Bedienung

Die Tabelle erhält eine schmale erste Checkboxspalte. Der Kopf wählt nur die
aktuelle Seite und zeigt den nativen teilweise ausgewählten Zustand. Markierte
Zeilen sind dezent hervorgehoben. Erst bei Auswahl erscheint oberhalb der
Tabelle die Aktionsleiste mit Anzahl, „Ausgewählte Verträge exportieren“ und
„Auswahl aufheben“. Eine einzelne Auswahl funktioniert ebenso wie mehrere.
Ohne Auswahl ist der Exportknopf deaktiviert und die Leiste verborgen.

Die Auswahl bleibt ausschließlich im aktuellen Dokument: kein Local Storage,
keine versteckte seitenübergreifende Sammlung. Filtereingaben, Seitenwechsel,
`pagehide` und `pageshow` einschließlich Back/Forward setzen sie zurück. Nach
„Auswahl aufheben“ geht der Fokus zur Kopf-Checkbox. Native Checkboxen sind
beschriftet und mit Leertaste bedienbar. Die Mehrfachauswahl benötigt JavaScript;
der bestehende Export aller Treffer bleibt auch ohne JavaScript erreichbar.

„Alle Treffer exportieren“ im Tabellenkopf behält die bisherige Filterung und
das Limit von 5.000 Datensätzen. Beide Aktionen sind sprachlich getrennt;
ausgewählte IDs sind ausschließlich echte Datenbank-IDs. Sidebar, Kennzahlen,
Filterpopover und vorhandene Vertrags-/Datenspalten wurden nicht umgestaltet.

Unter der Pagination steht „Verträge aus Excel importieren“ mit Kurzbeschreibung,
drei Schritten, Vorlagenlink, beschriftetem Dateifeld und separatem Importknopf.
Vor dem Absenden ist der Dateiname sichtbar. „Hinweise zum Excel-Import“ ist
standardmäßig geschlossen und dokumentiert Format, Grenzen, Pflichtfelder,
Referenzen, Duplikate, Datumswerte, verbotene Inhalte und atomare Verarbeitung.

Der Import bleibt unverändert create-only und atomar; keine Änderung der
Validierungsentscheidungen. Nur Meldungstexte wurden verständlicher bzw. deutsch
formuliert. Parserfehler werden für die Anzeige übersetzt, mit erhaltenem
Zeilen-/Zellbezug und normalem Jinja-Escaping. Bestätigte Backend-Ergebnisse
steuern weiterhin Erfolgsmeldungen oder die Fehlerseite; keine vorzeitigen Toasts.

## Serverseitiger Export

Neu: `POST /contracts/export-selected.xlsx` mit `csrf_token` und einem
kommagetrennten Feld `contract_ids`. Ein Feld für die ganze Auswahl hält auch
100 Zeilen innerhalb der bestehenden Grenze von 40 Formularfeldern. Globale
Request-/Multipart-/Feldgrößen wurden nicht gelockert.

- Anmeldung, aktiver Zugang, MFA/Passwortpflicht und CSRF werden wie bisher
  geprüft. Alle aktiven interaktiven Rollen durften bereits exportieren; eine
  zusätzliche Exportberechtigungsoption existiert im aktuellen Modell nicht.
  Die UI verwendet dieselbe aktive Zugangsprüfung. Kein neues Benutzerrecht.
- Strikte positive ASCII-IDs im Datenbankbereich; keine Tabellenpositionen,
  führenden Nullen, Dubletten, leeren Elemente oder frei interpretierten Zahlen.
- Leere/ungültige/doppelte ID-Auswahl: 422. Mehr als 5.000 IDs: 413.
  Zusätzliche/doppelte Formularfelder können bereits an der Formulargrenze mit
  400 scheitern. Ungültiges CSRF: 403; fehlende Sitzung: bestehende Weiterleitung.
- Ein gemeinsamer, objekt- und fachbereichsgeschützter Datenbankabruf vergleicht
  die vollständige Trefferanzahl mit den IDs. Jede nicht verfügbare oder nicht
  erlaubte ID führt zu 404 für die gesamte Auswahl, ohne zu verraten, welcher
  Eintrag fehlt. Keine teilweise erfolgreiche Datei und kein stilles Entfernen.
- Archivierte Verträge bleiben entsprechend den bestehenden Leserechten
  exportierbar. Der Export ändert weder Verträge noch Versionen/Vertragshistorie.
- Beide Exportwege verwenden denselben extrahierten Response-Generator:
  bestehende Spalten, XLSX-Serializer, 5.000-Zeilen-, 8-MiB- sowie 10-/15-Sekunden-
  Budgets. Text bleibt `inlineStr`; keine Formelauswertung. Keine Dokumente,
  Anhänge oder zusätzliche versteckte Arbeitsmappenbestandteile.
- Der neue Auswahl-Export schreibt nach erfolgreicher Dateierzeugung einen
  `contract_selection_export_prepared`-Eintrag über die vorhandene Audit-
  Infrastruktur: Akteur, Korrelations-ID, Anzahl und zulässige Vertrags-IDs.
  Keine Vertragsinhalte, Dateiinhalte oder Zugangsdaten. Erst nach erfolgreichem
  Audit-Commit wird die Datei ausgeliefert. Dies protokolliert die Vorbereitung,
  nicht einen beweisbaren Empfang beim Client. Bestehende Request-Protokollierung
  und das Verhalten des bisherigen GET-Exports bleiben erhalten.

## Tatsächliche Verifikation

| Prüfung | Ergebnis |
|---|---|
| Relevante sechs Pytest-Suites | **64 bestanden, 1 übersprungen**, 54,86 s |
| Zusätzlicher Export einer vollen 100-Zeilen-Seite und lokalisierter Formelimportfehler | **2 bestanden**, 2,49 s |
| Laufender Uvicorn-Preview: vier Rollen | **32 HTTP-Prüfungen bestanden**, echte XLSX-Antworten und Importvorgänge |
| JS-Syntax, Python-Kompilierung, `git diff --check` | bestanden |
| Browserlauf gegen committeten Stand | synthetische Anwendung gestartet, Playwright-Treiberstart mit `PermissionError / WinError 5` blockiert |
| Screenshots, Tastatur, Checkbox-Indeterminate, Back/Forward, 390/768/1280/1440 px | **nicht im Browser geprüft** |

Suites: `test_excel_selection.py`, `test_contract_toolbar.py`, `test_phase7.py`,
`test_phase8.py`, `test_frontend_redesign.py`, `test_acceptance.py`.
Der einzige Skip erfordert tatsächliche eingeschränkte PostgreSQL-Historienrechte;
er ist keine bestandene PostgreSQL-Prüfung. Eine bestehende Starlette-
Deprecation-Warnung bleibt. Keine neuen Last- oder vollständigen Gesamttestläufe
behauptet. Der neue PostgreSQL-/RLS-Pfad wurde hier nicht live ausgeführt.

Die Regression umfasst Einzel-/Mehrfach-/Seitenexport, gefilterten Gesamtexport,
leere und manipulierte IDs, Dubletten, fremde/fehlende Datensätze, widerrufene
Mitgliedschaft, CSRF, Gäste, Limits, Workbook-Struktur, wörtliche Formeltexte,
Auditdaten sowie bestehenden Import und Fachbereichsgrenzen. Der erste Lauf
fand unzutreffende Annahmen neuer Tests über wiederholte `no-store`-Header,
die Anzahl der XLSX-ZIP-Bestandteile und den früheren Parserfehlerstatus. Diese
Tests wurden auf die tatsächlichen bestehenden Schutzmechanismen korrigiert;
keine Sicherheitsprüfung wurde abgeschwächt.

Evidenz: [excel-selection.json](evidence/excel-selection.json).
Lokale Protokolle: `.verification/excel-final-tests.xml`, `excel-final-tests.txt`,
`excel-additional-tests.xml`, `excel-additional-tests.txt`, `excel-http.json`,
`excel-browser/result.json`. Keine Screenshots wurden aufgenommen oder inspiziert.

## Windows-Vorschau und ausstehende Browserabnahme

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
python scripts\preview_frontend.py --port 8790
```

Die aktuelle synthetische Vorschau läuft unter `http://localhost:8790/`.
Konten: `admin`, `kultur`, `bau`, `pruefer`. Reines Testpasswort:
`NurZumTesten-Starkes-Passwort-2026`. Nur Loopback, frische SQLite-Daten;
`Ctrl+C` beendet und bereinigt die Vorschau. Die HTTP-Prüfung hat ausschließlich
in dieser Wegwerf-Datenbank neue synthetische Importdatensätze erzeugt.

In einer für Browserprozesse autorisierten lokalen PowerShell mit Edge und den
vorhandenen Playwright-Abhängigkeiten:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
$excelRun = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts\verify_excel_selection.py --channel msedge --output ".verification\excel-$excelRun"
```

Der Prüfer verlangt committeten Code und startet selbst eine isolierte
synthetische Anwendung. Er prüft vier Rollen bei 390, 768, 1280 und 1440 px:
Checkboxen mit Maus/Tastatur, Teil-/Seitenauswahl, echte Downloads für ein/zwei/
alle Seitenobjekte, Aufheben, Pagination, Filterwechsel, Zurücknavigation,
Gesamtexport, Dateinamen sowie echte Importfehler und Erfolge. Die Aufnahmen
heißen `{Rolle}-default-{Breite}.png`, `selected-{Breite}.png`,
`import-{Breite}.png` sowie `import-error.png`/`import-success.png`, jeweils mit
Rollenpräfix. Für Prüfer entstehen keine Importbilder, da Import nicht erlaubt ist.

Nach erfolgreichem Lauf die tatsächlichen PNGs auf Überlauf, Ausrichtung,
Touchziele, Tabellenposition und Fokus prüfen und die visuelle Inspektion separat
mit Quellstand und Dateinamen protokollieren. `visual_inspection` bleibt bis dahin
`NOT_PERFORMED`; automatischer Erfolg ersetzt keine Sichtprüfung. Nur synthetische
Bilder und sanitisiertes JSON weitergeben, keine Cookies oder Zugangstoken.

Regression erneut:

```powershell
python -m pytest -q tests/test_excel_selection.py tests/test_contract_toolbar.py tests/test_phase7.py tests/test_phase8.py tests/test_frontend_redesign.py tests/test_acceptance.py --basetemp=.verification/excel-recheck -p no:cacheprovider
node --check app/static/interface.js
```

## Exakte Dateiliste

```text
app/listing.py
app/main.py
app/presentation.py
app/static/interface.js
app/static/site.css
app/templates/import_result.html
app/templates/list.html
scripts/verify_contract_toolbar.py
scripts/verify_excel_selection.py
tests/test_contract_toolbar.py
tests/test_excel_selection.py
docs/EXCEL_SELECTION_IMPLEMENTATION.md
docs/FRONTEND_IMPLEMENTATION_REPORT.md
docs/FRONTEND_ROUTE_MATRIX.md
docs/evidence/excel-selection.json
```

`docs/export.png`, `docs/import.png` und `docs/vertraege.png` bleiben unverändert
und unversioniert. Keine Datenbankmigration, STRATO-Änderung, Produktionsdaten,
kein Push, Merge oder Deployment. Frühere Release-Evidenz bleibt erhalten.
