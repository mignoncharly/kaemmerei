# OPEN.HERZ: Frontend-Designsystem

Die Implementierung bleibt serverseitig: FastAPI, Jinja, ein zentraler Stylesheet
und zwei kleine lokale Skripte. Keine externe Schrift, CDN, Build-Pipeline oder
zusätzliche Runtime-Abhängigkeit. Die bestehende Content Security Policy bleibt
streng; keine Inline-Styles oder Inline-Skripte.

## Grundlagen

| Token | Wert / Verwendung |
|---|---|
| `--nav` | `#172a3c`, feste Navigation |
| `--canvas` / `--surface` | `#f5f6f8` / `#ffffff`, Arbeitsfläche / Panels |
| `--ink` / `--muted` | `#243348` / `#59687a`, Text / ergänzende Angaben |
| `--accent` | `#126b75`, Hauptaktionen und Links |
| `--success` / `--warning` / `--danger` | `#216443` / `#805313` / `#a1333d` |
| `--border` | `#dce2e8`, Trennlinien |
| Schrift | Inter, falls lokal vorhanden; sonst Segoe UI / Systemschrift |
| Abstände | 4, 8, 12, 16, 20, 24, 32, 40 px |
| Radien | 6 px für Eingaben, 8–10 px für Bereiche |
| Sidebar | 248 px, dauerhaft ab 1001 px |
| Inhaltsbreite | maximal 1600 px innerhalb des Arbeitsbereichs |

## Wiederverwendbare Muster

- `base.html`: Sidebar, Breadcrumb, Kontomenü, Footer, Pilot- und Erfolgshinweise.
- `components.html`: SVG-Icons, aktive Navigationslinks, leere Zustände.
- `partials/metrics.html`, `partials/reminders.html`: berechtigungsgefilterte
  Kennzahlen und Fristen, gemeinsam in Bestand und Überblick.
- `.page-head`, `.panel`, `.panel-heading`, `.panel-body`: Seitenhierarchie.
- `.form-section` mit `fieldset/legend`, `.form-grid`, `.form-actions`: Formulare.
- `.button.primary/secondary/subtle/danger`: eindeutig abgestufte Aktionen.
- `.table-scroll`, `.pagination`, `.filter-form`: beschriftete Datenregionen;
  native GET-Filter und serverseitige Pagination bleiben erhalten.
- `.tag`, `.task-status-*`, `.review-status-*`: ausgeschriebene Statusangaben,
  ergänzt durch Farbe. Keine alleinige Farbcodierung.
- `.alert`, `.notice`, `.field-error`, `.submission-status`: Fehler bleiben
  sichtbar; Prozesshinweise erscheinen erst bei Formularversand. Keine
  vorweggenommenen Erfolgsmeldungen und keine simulierten Upload-Prozentwerte.
- Native `details/summary`: Kontomenü, technische Angaben, Import,
  Abschnittserweiterungen und die bestehende Archivierungsbestätigung.
- `.section-nav`: echte Abschnittslinks auf der Vertragsdetailseite. Keine
  versteckten Tab-Inhalte oder zusätzlichen Requests.

## Responsive und zugänglich

Unter 1001 px wird die Navigation mit JavaScript zum Drawer; ohne JavaScript
bleibt eine sichtbare Navigation im Dokumentfluss. Der Drawer setzt den übrigen
Arbeitsbereich `inert`, hält den Tastaturfokus und schließt mit Escape; danach
kehrt der Fokus zur Öffnen-Schaltfläche zurück. Name, Zustand und Dialogrolle
werden gesetzt. Desktopnavigation benötigt keine Fokusfalle.

Formulare werden einspaltig, Tabellen scrollen innerhalb einer beschrifteten,
fokussierbaren Region. Alle Aktionen bleiben als native Links/Formulare nutzbar.
Fehler erhalten Fokus, native Validierungsfehler zusätzlich Inline-Text und
`aria-invalid`/`aria-describedby`. Alle Seiten haben einen Skip-Link, Hauptinhalt,
deutsche Sprache und sichtbare Fokusumrandungen. Reduzierte Bewegung und
Druckdarstellung sind berücksichtigt.

Die technische Umsetzung ist kein WCAG-Zertifikat. Tatsächliche Browser-,
Screenreader-, Zoom- und Screenshot-Abnahme siehe Implementierungsbericht.
