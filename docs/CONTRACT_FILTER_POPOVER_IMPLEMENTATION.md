# Vertragsübersicht: Korrektur auf „Suche & Filter“

Stand: 22.10.2026. Branch `redesign/frontend-dashboard`.
Implementierung: `c3bd73274fe2ed7e545341380fefaca8d2f6d5cb`.
Vergleichsbasis: `a36fb9374939dd45ab2a576277ad579d9eff6020`.

**Die Korrektur ist implementiert und funktional geprüft. Die visuelle und
interaktive Browserabnahme bleibt blockiert und ist nicht bestanden.**
Dieser Bericht ersetzt die Layoutbeschreibung der früheren permanenten Toolbar.

## Konkrete Änderungen

- Im Seitenkopf stehen „Suche & Filter“ und unmittelbar daneben die bestehende
  berechtigungsabhängige Aktion „+ Vertrag erfassen“. Keine dauerhaft sichtbare
  Suche und kein separater Suchknopf mehr.
- Der komplette GET-Such-/Filterbogen öffnet sich als am Auslöser positionierter
  Dialog. Desktop: schwebendes Popover mit begrenzter Höhe; bis 700 px: rechter,
  auf kleinen Telefonen bildschirmbreiter Drawer. Der Dialog liegt über der
  Seite und belegt keinen Platz im normalen Seitenlayout.
- Native Dialogmechanik übernimmt modalen Hintergrund, Fokusbegrenzung und
  Escape. Schließen-Schaltfläche und Klick außerhalb schließen ebenfalls;
  Fokus kehrt zum Auslöser zurück. Beim Öffnen wird das Suchfeld fokussiert.
  `aria-expanded`, `aria-controls` und ein benannter Dialog sind vorhanden.
  Werte bleiben beim Schließen/Öffnen erhalten. Ungültige Felder öffnen das Panel.
- Ohne Dialog-Unterstützung bzw. ohne JavaScript bleibt derselbe Formularbogen
  über ein natives Disclosure erreichbar. Es gibt weiterhin genau ein Formular
  und ein Suchfeld; keine verschachtelten Formulare oder Kopien von Controls.
- Fünf Kennzahlen erscheinen als schmale gemeinsame Zeile statt als große
  Karten. Zahlen und verlinkte Statusbereiche verwenden dieselben erlaubten
  Abfragen. Keine Änderungen am Dashboard-Partial oder an anderen Seiten.
- Ohne Fristen genügt eine kompakte Statuszeile. Bei realen Fristen sind die
  Zahlen für Überfälliges und Anstehendes in einem hervorgehobenen Hinweis
  sichtbar; dessen Disclosure enthält die bisherigen Fristendetails und Links.
- Aktive Suche und Filter erscheinen nur bei Anwendung als Chips. Der
  Suchbegriff wird jetzt mitgezählt, weil auch das Suchfeld verborgen ist.
  Einzelentfernung erhält alle anderen Parameter und setzt die Ergebnisseite
  zurück. „Zurücksetzen“ leert Suche und erweiterte Filter gemeinsam; die
  ausgewählte Seitengröße bleibt erhalten und zählt nicht als aktiver Filter.
- Der Tabellenkopf enthält echte Trefferzahl, Anzahl auf der aktuellen Seite
  und „Excel exportieren“ mit Hinweis „Alle Treffer · max. 5.000“.
  Tabelle, Pagination und nachgelagerter Excel-Import bleiben erhalten.
- Das bestehende Designsystem bleibt maßgeblich. Neue Layoutregeln sind auf die
  Vertragsübersicht und ihren Dialog beschränkt. Bewegungen respektieren
  `prefers-reduced-motion`.

Suchabfragen, Datenumfang, Sortierung, Pagination, Exporthandler, Berechtigungen,
Vertragszugriff und Datenbank wurden nicht geändert. Der Python-Helper erzeugt
weiterhin ausschließlich Darstellungslinks. Keine neuen Abhängigkeiten.

## Tatsächlich ausgeführte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Vier relevante Pytest-Suites | **23 bestanden**, keine Skips, 16,80 s |
| Rollen Admin, Fachbereich, Prüfer | Kombinationen, Trefferzahlen, Chip-Entfernung, Reset, Pagination und XLSX-Inhalt bestanden |
| Fachbereichsisolation | Fremder Datensatz nicht auffindbar, Detailzugriff 404 |
| HTML und Darstellungswerte | Eindeutige IDs, zugeordnete Labels, ein Suchfeld im geschlossenen Bereich, geschützte Erfassungsaktion, gleiche Kennzahlen wie Dashboard, Export im Tabellenkopf bestanden |
| Laufender synthetischer Preview | **15 HTTP-Prüfungen bestanden**, inklusive drei Ansichten und CSS/JS je Rolle |
| JavaScript-Syntax, Python-Kompilierung, Diff-Prüfung | bestanden |
| Browser-Connector | Keine Browserinstanz verfügbar |
| Playwright gegen committeten Code | Synthetische Anwendung gestartet; Treiberstart mit `PermissionError / WinError 5` blockiert |
| Screenshots / visuelle Inspektion | **Nicht durchgeführt**, keine tatsächlichen Screenshots verfügbar |
| 390, 768, 1280, 1440 px / Keyboard / Fokus / Drawer / CSP im Browser | **Nicht durchgeführt**, lokale Browserabnahme erforderlich |
| Höhenvergleich erste Tabellenzeile | **Nicht gemessen**, keine visuelle Verbesserung als gemessen ausgegeben |

Tests: `test_contract_toolbar.py`, `test_frontend_redesign.py`, `test_phase8.py`,
`test_report_projection.py`. Eine bestehende Starlette-TestClient-Warnung bleibt.
Die Chip-Tests wurden gezielt an die korrigierte Anforderung angepasst: Suchtext
ist nun ein Chip und vollständiges Zurücksetzen leert ihn. Bestehende Export-,
Pagination- und Berechtigungsprüfungen bleiben erhalten.

Lokale Ergebnisse: `.verification/popover-tests.txt`, `popover-tests.xml`,
`popover-http.json`, `popover-browser/result.json`.
[Sanitisierte Evidenz](evidence/contract-filter-popover.json).
Frühere U026-/Gesamtredesign-Nachweise bleiben unverändert. Kein neuer
PostgreSQL-, Last- oder vollständiger Gesamtsuitenlauf behauptet.

## Lokal prüfen

Der synthetische Preview wurde auf `http://localhost:8788/` gestartet.
Er kann in einer lokalen PowerShell erneut gestartet werden:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
python scripts\preview_frontend.py --port 8788
```

Testkonten: `admin`, `kultur`, `bau`, `pruefer`.
Reines Testpasswort: `NurZumTesten-Starkes-Passwort-2026`.
Ausschließlich Loopback und frische synthetische SQLite-Daten; `Ctrl+C` beendet
die Vorschau und bereinigt die temporären Daten.

In einer für Browserprozesse autorisierten lokalen PowerShell mit installiertem
Edge und den vorhandenen Browserabhängigkeiten:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Redesign'
$popoverRun = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts\verify_contract_toolbar.py --channel msedge --output ".verification\popover-$popoverRun"
```

Der Prüfer verlangt einen committeten Codezustand und startet eine eigene
synthetische Anwendung. Die bisherige Toolbar wird mit ihrem echten Jinja-
Template und ihren Assets aus `a36fb93` gegen dieselbe Datenbank gerendert.
Kein Mockup und kein Austausch versionierter Dateien.

Geplante Aufnahmen für 390/768/1280/1440 px:

- `before-{Breite}.png`: vorherige Toolbar.
- `after-{Rolle}-{Breite}.png`: korrigierte Standardansicht.
- `expanded-{Rolle}-{Breite}.png`: geöffnetes Popover bzw. Drawer.
- `active-{Rolle}-{Breite}.png`: angewandte Suche und Filter.

Rollen: `admin`, `kultur`, `pruefer`. Automatische Szenarien umfassen Enter-
Suche, Tastaturöffnung, Anfangsfokus, Fokusbegrenzung, Escape mit Fokusrückkehr,
Klick außerhalb auf Desktop/Tablet, Schließen-Knopf, Werterhalt, Chips, Reset,
Back/Forward, Pagination, XLSX-Inhalt, Isolation, reduzierte Bewegung und
JavaScript-freie Bedienung. Zudem werden horizontaler Überlauf und unveränderte
Tabellenposition beim Öffnen geprüft. Prüfziel gegenüber der bisherigen
Toolbar: erste Zeile mindestens 100 px höher, Desktop zusätzlich unter 900 px.

Diese Ziele sind **noch keine gemessenen Ergebnisse**. Nach erfolgreichem Lauf
die tatsächlichen PNGs prüfen und eine separate Inspektionsnotiz mit Quellstand,
Breiten, Dateinamen, Befunden und ggf. Korrekturen ablegen. `visual_inspection`
bleibt im automatischen Ergebnis absichtlich `NOT_PERFORMED`. Keine Cookies,
Tokens, produktiven Daten oder Roh-Ausnahmen weitergeben.

## Exakte Dateiliste

```text
app/presentation.py
app/static/interface.js
app/static/site.css
app/templates/list.html
scripts/verify_contract_toolbar.py
tests/test_contract_toolbar.py
docs/CONTRACT_FILTER_POPOVER_IMPLEMENTATION.md
docs/CONTRACT_TOOLBAR_IMPLEMENTATION.md
docs/FRONTEND_IMPLEMENTATION_REPORT.md
docs/evidence/contract-filter-popover.json
```

Die vom Nutzer hinzugefügte Referenz `docs/vertraege.png` bleibt unverändert
und unversioniert (SHA-256
`01a4bed8ef6d19e6c740230d781365911630c2147e033b0583622c1ceb701847`).
Kein Push, Merge, Deployment oder STRATO-Zugriff.
