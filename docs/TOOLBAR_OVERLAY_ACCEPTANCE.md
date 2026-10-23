# Toolbar-Overlay: Korrektur des Browservergleichs

Stand: 23.10.2026. Kanonisches Projekt, Branch `release/redesign-integration`.
Ausgangsstand `d5f402d9f93d25231fb40aa843395da70f5267eb`, Korrektur-Commit
`dc881b3e3040dd228eb016fc2623964d4687ac2f`.

## Erhaltene Benutzerergebnisse

Verzeichnis:
`.verification/integrated-browsers-d6a513c6d9e64dbb912f37f141b36898/`.

- Redesign: **373 Browserprüfungen bestanden**, einschließlich MFA.
- Toolbar: acht Prüfungen aufgezeichnet, dann
  `admin_overlay_no_layout_shift_390` fehlgeschlagen.
- Excel: durch den korrekt abbrechenden Launcher **nicht ausgeführt**.

Die ursprünglichen JSON-Berichte, Logs und PNG-Dateien wurden nicht geändert.
Der Redesign-Bericht misst für die geschlossene Administrator-Vertragsübersicht
bei 390/768/1280/1440 px jeweils genau die entsprechende Seitenbreite, ohne
Überlauf. Das ist ein Nachweis für `d5f402d`, keine vollständige neue Abnahme.

## Bestätigter Fehler im Vergleichsablauf

Die bisherige Assertion verglich ausschließlich die viewportbezogene Y-Koordinate
der ersten Tabellenzeile vor und nach dem Öffnen. Der Ausgangswert wurde jedoch
**vor `toggle.focus()`** erfasst. Der vorhergehende zusätzliche Tabellen-Scrolltest
hatte die große Tabelle fokussiert und `End` gedrückt. Diese Taste ist kein Befehl
zum horizontalen Tabellen-Scrollen; sie kann die Seite vertikal scrollen. Ein
einzelnes `window.scrollTo(0,0)` war keine verlässliche Trennung dieses Tests vom
anschließenden Vergleich und der zwischenliegenden Vollseitenaufnahme.

Der gespeicherte Bericht belegt den fehlerhaften Ausgangszustand: Bereits **vor
dem Öffnen** steht `first_row_positions.390.after` auf **−1616,796875 px**. Die
geschlossene Seite und auch der horizontal gescrollte Tabellenzustand hatten
dagegen `pageWidth = viewport = 390`. Das Fokussieren des nun außerhalb des
Viewports liegenden Headerbuttons bringt ihn wieder in den sichtbaren Bereich.
Der Vergleich umfasste damit zwei verschiedene Scroll-/Fokuszustände und schrieb
deren Differenz fälschlich dem Dialog zu. Auch die bisherige Prüfung
`rows_higher_390` war mit diesem negativen Viewportwert nicht belastbar.

Die alten Artefakte enthalten keinen Y-Wert nach dem Öffnen, keine vertikalen
Scrollstände und keine geöffnete Aufnahme: Die Assertion brach vor der Aufnahme
ab. Deshalb lässt sich die genaue Nachher-Differenz oder der zeitliche Anteil von
Tastatur-Scrolling, Fokus und Vollseitenaufnahme nicht numerisch rekonstruieren.
Eine Änderung der Dokumenthöhe oder ein Anwendungs-Reflow beim Öffnen ist durch
diese Daten **nicht belegt**. Der nachgewiesene Fehler liegt in der Testgrenze.

## Implementierte Korrektur ohne Lockerung

- Horizontale Tastaturprüfung nach den Overlayprüfungen, mit `ArrowRight`,
  geprüftem `scrollLeft` und `focus({preventScroll:true})`. Kein `End`, kein
  nachträgliches Zurücksetzen des Seiten-Scrollstands als Reparatur.
- Der geschlossene Ausgangszustand muss am Seitenursprung liegen. Die Höhe der
  ersten Tabellenzeile wird in Dokumentkoordinaten verglichen; eine sichtbare
  Desktopzeile muss auch eine **nichtnegative** Viewportkoordinate haben.
- Der Filterbutton wird **vor** der Öffnungs-Baseline fokussiert. Für den bereits
  sichtbaren Button muss zusätzlich auch dieser Fokuswechsel verschiebungsfrei
  bleiben.
- Vor/nach Öffnen und Schließen werden Dokument- und Viewportkoordinaten,
  Zeilenmaße, Fenster- und Dokumentmaße, Clientbreite/-höhe, Seiten-Scrollstand und
  Tabellen-Scrollstand gespeichert. Dieselbe strenge Toleranz von unter 2 px gilt
  für alle Größen. Unveränderter horizontaler Seitenüberlauf wird ebenfalls
  abgelehnt. Scrollen kann einen echten Reflow nicht verdecken und umgekehrt.
- Bei 390/768/1280/1440 px und allen bisherigen Toolbar-Rollen werden geschlossene
  und geöffnete Aufnahmen erstellt. Die geöffnete Aufnahme entsteht **vor** der
  problematischen Assertion, damit ein erneuter Fehler seinen Nachweis behält.
- Die bisherigen Fokus-, Escape-, Popover-, Such-, Export- und Rollenprüfungen
  bleiben bestehen. Zusätzlich wird die Geometrie nach dem Schließen geprüft.

Anwendungs-CSS/-JavaScript, Dialog-/Drawer-Verhalten, Backend, MFA, Rechte und
Excel-Exportlogik wurden nicht geändert. Der gemeinsame Fail-fast-Launcher ist
ebenfalls unverändert.

## Dateien und tatsächlich ausgeführte Tests

Codeänderungen:

1. `scripts/browser_layout.py`: gemeinsame Geometrieerfassung, strenger Vergleich,
   Fokus vor Baseline.
2. `scripts/verify_contract_toolbar.py`: getrennte Szenarien, Dokumentkoordinaten,
   zusätzliche Nachweise und Assertions.
3. `tests/test_toolbar_geometry.py`: 27 Regressionen, darunter das negative
   Ausgangs-Y, alle vier Breiten, alle Messgrößen, verdeckte Verschiebungen und
   ungültige Messwerte. Die modellierten Geometrien sind Unit-Testdaten, keine
   behaupteten Browsermessungen.

Zuerst gezielt: **27 bestanden**, 0,10 s;
`.verification/toolbar-overlay-targeted.xml`.

Danach Frontend-/Toolbar-/Excel-/Diagnose- und Launcherregressionen:
**123 bestanden**, keine Skips/Fehler, 29,94 s;
`.verification/toolbar-overlay-regressions.xml`.
Die Tests liefen auf dem anschließend unverändert als `dc881b3` versionierten
Codestand. Eine bestehende Starlette-Deprecation-Warnung ist kein Testfehler.

Kein erneuter vollständiger PostgreSQL-Lauf: Es änderten sich ausschließlich
Prüfinfrastruktur und Tests. Der tatsächliche PostgreSQL-Nachweis bleibt an
`d5f402d` gebunden (521 bestanden, 2 Umgebungs-Skips, 15 Untertests).

Der gemeinsame PowerShell-Aufruf wurde auf `dc881b3` hier tatsächlich versucht:
**Exitcode 1**, `automation_driver_permission_denied`, **WinError 5**. Die beiden
weiteren Suiten wurden korrekt nicht gestartet. Nachweis:
`.verification/integrated-browsers-ec1fb13ecc6f47f09401e1b6369fc456/`.
Keine neue Browseraufnahme wurde in dieser Umgebung erzeugt.

## Sichtprüfung und erneuter Benutzerlauf

Angesehen wurden die tatsächlichen bisherigen Aufnahmen
`toolbar/after-admin-390.png`, `redesign/admin-contracts-390.png` und
`redesign/admin-contracts-1440.png`. Die Vertragsübersicht ist innerhalb der
Seitenbreite; die breite Tabelle scrollt lokal. Der Import ist mobil gestapelt
und auf Desktop in einer einheitlichen Reihe angeordnet. Die Toolbar-Aufnahme
zeigt den fokussierten großen Tabellenbereich. Diese Sichtprüfung betrifft den
vorhandenen Stand und enthält **keinen Nachweis des geöffneten Filterdialogs**.

Ein vollständiger Aufruf unter dem normalen autorisierten Windows-Konto:

```powershell
powershell.exe -NoProfile -File "C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-IntegratedBrowserVerification.ps1" -ExpectedSource dc881b3e3040dd228eb016fc2623964d4687ac2f -Channel msedge
```

Er erzeugt ein neues isoliertes Nachweisverzeichnis, kontrolliert SHA und saubere
relevante Quellen vor/nach jedem Kind und bewahrt jeden tatsächlichen Exitcode.
`SUCCESS` erscheint nur nach drei gültigen erfolgreichen Suiten. Anschließend
die Aufnahmen `after-*`, `open-*`, `expanded-*`, die Excel-Aufnahmen und die
Geometrieeinträge `*_closed_*`, `*_focused_closed_*`, `*_open_*`,
`*_closed_again_*` aller vier Breiten prüfen.

**Abnahme offen / RELEASE READY: nein.** Erforderlich bleiben drei erfolgreiche
Browser-Suiten auf derselben Revision und die Prüfung ihrer tatsächlichen Bilder.
Vorhandene lokale Dokumentationsänderungen bleiben erhalten; dieser Bericht und
die aktualisierte Release-Übersicht liegen ebenfalls lokal uncommitted vor.
Kein Push, Merge, Deployment, STRATO- oder Produktionszugriff.
