# Vertragsübersicht: kompakte Suche und Filter

Stand: 22.10.2026. Worktree `OPEN_HERZ_Vertragsregister_Redesign`, Branch
`redesign/frontend-dashboard`. Ausgangsstand:
`e4c3740833b9ac77befcec91b0c6cfa05be8d63b`.

Die Implementierung und funktionale Regression sind abgeschlossen. Die
Browserabnahme einschließlich Screenshots und tatsächlicher Höhenmessung bleibt
bis zu einem erfolgreichen lokalen Browserlauf offen.

## Umsetzung

- Eine kompakte Toolbar enthält die immer sichtbare Suche, Filter-Schaltfläche
  mit Anzahl und die bestehende, berechtigungsabhängige Erfassungsaktion.
- Ein geschlossenes natives `details` enthält sämtliche bisherigen erweiterten
  Filter. JavaScript ergänzt die außenliegende Schaltfläche mit
  `aria-expanded`/`aria-controls`. Ohne JavaScript bleibt das native Disclosure
  bedienbar. Es gibt genau ein GET-Formular und ein Suchfeld.
- Geschlossene Felder bleiben Teil der Formularübertragung. Enter in der Suche
  und „Filter anwenden“ verwenden unverändert die serverseitige Suche.
- Chips zeigen normalisierte Filter einschließlich eines gegebenenfalls aktiven
  KPI-Fokus. Suchtext und Seitengröße werden nicht als erweiterte Filter gezählt.
  Einzelentfernung bewahrt alle anderen Filter, Suche und Seitengröße; sie setzt
  lediglich die Ergebnisseite zurück. Zurücksetzen entfernt die erweiterten
  Filter, behält aber Suchtext und Seitengröße. „Suche löschen“ erhält die Filter.
- Der Exportlink bleibt neben der tatsächlichen Trefferzahl sichtbar. Er nutzt
  die angewendeten Filter des angezeigten Ergebnisses, unabhängig von noch nicht
  abgesendeten Formularänderungen. Der Hinweis erklärt den Export aller Treffer
  bis zur bestehenden Grenze von 5.000; der XLSX-Handler bleibt unverändert.
- Tabelle und Pagination bleiben erhalten. Der Importbereich steht nun darunter.
  KPI-Abstände, Warnbereich und Toolbar sind ausschließlich auf dieser Seite
  verdichtet; Sidebar und andere Seiten behalten ihr bestehendes Design.
- Responsive Filter: drei, zwei bzw. eine Spalte. Mobil steht die Suche in einer
  eigenen Zeile; Chips umbrechen. Vorhandene Tokens und Fokusmarkierungen werden
  verwendet. Die kurze Öffnungsanimation respektiert reduzierte Bewegung.
- Chip-Navigation führt den Tastaturfokus nach dem Reload zum Filterknopf;
  Suchlöschung zum Suchfeld. Ungültige Felder im Filterpanel öffnen es vor dem
  Fokussieren. Browser-Back/Forward synchronisiert den Disclosure-Zustand.

Keine Migration, neue Abhängigkeit, Änderung an Berechtigungen, Filterabfragen,
Sortierung, Exportgrenzen oder Geschäftsregeln. Der Python-Zusatz erzeugt nur
Darstellungswerte und Links aus bereits normalisierten Parametern.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `test_contract_toolbar.py`, `test_frontend_redesign.py`, `test_phase8.py`, `test_report_projection.py` | **22 bestanden**, keine Skips, 16,14 s |
| Rollen Admin/Fachbereich/Prüfer | Realer TestClient: kombinierte Filter, Zähler, Chip-Entfernung, Reset, Pagination und XLSX-Inhalt bestanden |
| Isolation | Fremder Fachbereich liefert keinen Treffer, fremder Vertragsdetailzugriff 404 |
| HTML | Eindeutige IDs, Labels, keine verschachtelten Formulare; Query-Escaping und nicht standardmäßige gültige Seitengröße geprüft |
| Laufender synthetischer Uvicorn-Preview | **15 HTTP-Prüfungen bestanden**: drei Ansichten und zwei Assets je Rolle |
| JavaScript / Python / Diff | `node --check`, `compileall`, `git diff --check` bestanden |
| Browser vor Änderung | Blockiert bei `automation_driver`, `PermissionError`, `WinError 5`; Browserstart nicht erreicht |
| Browser nach Änderung | Ebenfalls blockiert bei `automation_driver`, `PermissionError`, `WinError 5`; kein Browser gestartet |
| 390/768/1280/1440 px, Tastatur, Back/Forward, reduzierte Bewegung, visuelle Höhenmessung | **Offen**, im lokalen Browser nachzuprüfen |
| Vorher/Nachher-Screenshots | **Keine erzeugt oder inspiziert**, solange Browserstart blockiert ist |

Eine bestehende Starlette-TestClient-Deprecation-Warnung bleibt bestehen.
Protokolle: `.verification/toolbar-tests.txt`, `toolbar-tests.xml`,
`toolbar-http.json`, `toolbar-before-browser/result.json`.
Die früheren Gesamttest-/U026-Nachweise bleiben unverändert; sie werden hier
nicht als neuer Gesamtlauf ausgegeben. PostgreSQL und Lastziele wurden für
diese Darstellungsänderung nicht erneut gemessen.

Implementierungscommit: `8fd11806d5065da8a4a6e140b69b7957f475088c`.
Der erneute Browserlauf gegen diesen sauberen Quellstand startete die
synthetische Anwendung, scheiterte aber bereits beim Start des Playwright-
Treibers. `.verification/toolbar-after-browser/result.json` enthält keine
Screenshots und ausdrücklich `visual_inspection: NOT_PERFORMED`.
[Sanitisierte Toolbar-Evidenz](evidence/contract-toolbar.json) hält beide
Browserblockaden und die tatsächlich bestandenen Prüfungen fest.

## Lokale Windows-Verifikation

Vorschau mit frischer synthetischer Datenbank, ausschließlich Loopback:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
python scripts\preview_frontend.py --port 8786
```

`http://localhost:8786/` öffnen. Testkonten `admin`, `kultur`, `bau`, `pruefer`;
reines Testpasswort `NurZumTesten-Starkes-Passwort-2026`. Mit `Ctrl+C` beenden.
Falls der Preview bereits auf diesem Port läuft, dessen URL direkt verwenden.

Der bestehende lokale Playwright-Workflow benötigt eine für Browserprozesse
autorisierte normale PowerShell mit installiertem Edge. Der Prüfer verlangt
einen committeten Quellstand und erzeugt selbst eine separate synthetische
Anwendung; er verbindet sich nicht mit einer produktiven Instanz:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
$toolbarRun = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts\verify_contract_toolbar.py --channel msedge --output ".verification\toolbar-$toolbarRun"
```

Die vorhandenen Abhängigkeiten werden wie im
[Frontendbericht](FRONTEND_IMPLEMENTATION_REPORT.md) bereitgestellt. Es sind
keine Sicherheitslockerungen oder Änderungen an STRATO erforderlich.

Der Prüfer rendert das tatsächliche alte Listentemplate und dessen Assets aus
dem oben genannten Git-Stand gegen dieselbe neue synthetische Datenbank wie die
aktuelle Seite. Er verändert keine versionierten Dateien. Nach erfolgreichem
Lauf enthält der Ausgabeordner:

- `before-{390,768,1280,1440}.png`
- `after-{admin,kultur,pruefer}-{390,768,1280,1440}.png`
- `expanded-{390,768,1280,1440}.png`
- `result.json` mit Quellcommit, Baseline, Browser-Version, Checks und Position
  der ersten Tabellenzeile vor/nach Änderung.

Die automatischen Szenarien prüfen Eingabe/Enter, Auf-/Zuklappen mit Tastatur,
erhaltene Werte, kombinierte Filter, Entfernung mit Fokus, Reset, Back/Forward,
Pagination, tatsächlichen XLSX-Download, Rechte und Bedienung ohne JavaScript.
Die erste Zeile muss bei allen vier Breiten mehr als 100 px höher liegen; auf
Desktop zusätzlich innerhalb der ersten 900 px. Dies ist ein Prüfziel, kein
bereits gemessenes Ergebnis.

Die PNGs anschließend tatsächlich auf Überlauf, Ausrichtung, Beschriftungen,
Lesbarkeit, Fokus und Abstand zur Tabelle ansehen. Zusätzlich Tab-Reihenfolge,
200-%-Zoom und reduzierte Bewegung prüfen. Ein automatisches `passed` ersetzt
keine visuelle Abnahme: `visual_inspection` bleibt absichtlich `NOT_PERFORMED`,
bis eine separate Inspektionsnotiz mit Quellstand, Prüfergebnis, Breiten und
Screenshot-Dateinamen abgelegt wird. Nur synthetische Screenshots und die
sanitisierte `result.json` weitergeben; keine Cookies, Tokens oder Zugangsdaten.

Regression erneut ausführen:

```powershell
python -m pytest -q tests/test_contract_toolbar.py tests/test_frontend_redesign.py tests/test_phase8.py tests/test_report_projection.py --basetemp=.verification/toolbar-recheck -p no:cacheprovider
node --check app/static/interface.js
```

## Geänderte Dateien

```text
app/main.py
app/presentation.py
app/static/interface.js
app/static/site.css
app/templates/list.html
scripts/verify_contract_toolbar.py
tests/test_contract_toolbar.py
docs/CONTRACT_TOOLBAR_IMPLEMENTATION.md
docs/FRONTEND_IMPLEMENTATION_REPORT.md
docs/evidence/contract-toolbar.json
```

Andere Seiten, Original-Worktree und bisherige Release-Evidenz wurden nicht
überarbeitet. Kein Push, Merge oder Deployment.
