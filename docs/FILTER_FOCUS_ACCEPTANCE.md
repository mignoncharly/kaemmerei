# Filterdialog: Fokusführung und integrierte Browserabnahme

Stand 23.10.2026. Kanonisches Projekt, Branch `release/redesign-integration`.
Korrekturcommit: `e1f262bbfe4ff4a039afa3a49aad995a5ac3efcf`.
Keine Änderung an CSS, Templates, Backend, Berechtigungen, MFA oder Excel-Verarbeitung.

## Tatsächlicher Befund

Unverändert erhaltene Benutzerevidenz auf `dc881b3e3040dd228eb016fc2623964d4687ac2f`:
`.verification/integrated-browsers-3acc4eb9d49f451fbcc5ee4eb521e0ad/`.
Redesign: **373 Checks bestanden**. Toolbar: **12 Checks bestanden**, danach
`admin_focus_contained_390` fehlgeschlagen. Excel: nicht ausgeführt.
`admin_overlay_no_layout_shift_390` hat bestanden und wird nicht verändert.

Der Runner setzt den Fokus auf den letzten Dialog-Link **Zurücksetzen** und drückt
`Tab`. Die bisherige Assertion prüft, ob `document.activeElement` im Dialog liegt.
Sie schlägt fehl: Das danach aktive Element lag außerhalb des Dialogs. Erwartet
ist beim zyklischen Vorwärtslauf die erste Schaltfläche **Schließen**.
Der alte Bericht speichert weder das konkrete aktive Element noch `document.hasFocus()`.
Ob `body` oder ein anderer Fokuszustand vorlag, lässt sich daraus nicht rekonstruieren;
ein Wechsel in die Browseroberfläche ist keine nachgewiesene Einzelmessung.
Die tatsächlich angesehene Aufnahme `toolbar/expanded-admin-390.png` zeigt den
offenen Drawer mit Suchfeldfokus **vor** dieser Interaktion, nicht ihren Fehlerzustand.

Der Filter ist auf allen Breiten ein **modaler** nativer `<dialog>`, geöffnet mit
`showModal()`. Die Seite im Hintergrund wird dabei nativ inert; der Dialog selbst
darf nicht über einen inerten Vorfahren deaktiviert werden. Der bisherige Code
enthielt Initialfokus, natives Escape und Fokus-Rückgabe beim Schließen, aber
keinen eigenen zyklischen Tab-Umlauf. Er verließ sich dafür vollständig auf das
native Verhalten. Genau diese Anforderung wurde im vorliegenden Edge-Lauf nicht
erfüllt. Die Assertion ist berechtigt; sie wird nicht abgeschwächt.

Das Formular wird einmal synchron in den Dialog verschoben. Zwischen dem expliziten
Fokussieren des Reset-Links und Tab gibt es keinen asynchronen Formular-Neuaufbau.
Initialfokus und Aufklappen haben im alten Lauf bestanden. Es gibt keinen Nachweis
für einen Timer-/Renderingfehler; der Fix benötigt keine Verzögerung oder Wiederholung
bis zu einem zufällig erfolgreichen Fokuszustand.

## Implementierte Korrektur

- Dialoglokaler Keydown-Handler: Tab am letzten Element fokussiert das erste;
  Shift+Tab am ersten fokussiert das letzte. Die normale Reihenfolge im Inneren,
  Escape und Ctrl-/Alt-/Meta-Tastenkombinationen bleiben erhalten.
- Die aktuell erreichbaren Elemente werden bei jedem Tastendruck neu bestimmt.
  Deaktivierte, versteckte, inerte, unsichtbare und negative Tabindex-Elemente
  werden übersprungen. Es werden keine positiven Tabindizes eingeführt.
- Explizites `aria-modal="true"`; `aria-controls` des Schalters referenziert den
  tatsächlich erzeugten Dialog. `aria-expanded`, Suchfeld-Initialfokus, natives
  Hintergrund-Inert-Verhalten und Rückgabe an den Schalter bleiben erhalten.
- Browserregression prüft bei **390, 768, 1280 und 1440 px** für **admin, kultur,
  bau und pruefer**: Ausgangsfokus, konkretes Vorwärtsziel unmittelbar und im
  nächsten Animation Frame, Rückwärtsziel, abgewehrten Hintergrundfokus,
  Escape-Rückgabe und Suchfeldfokus beim erneuten Öffnen. Beide Vorwärtsmessungen
  müssen bestehen. Bestehende Geometrie-/Overflow-Prüfungen bleiben unverändert.

`focus_measurements` im lokalen `toolbar/result.json` protokolliert pro Schritt
`expected_target`, `actual_target`, Übereinstimmung, Dialogzugehörigkeit,
Dokumentfokus und Modal-/ARIA-Zustand. Zielnamen sind feste Kennungen wie `close`,
`reset`, `search`, `toggle`, `body`, `other_inside` oder `other_outside`.
Keine Feldwerte, DOM-Texte, HTML, URLs, dynamischen Element-IDs, Passwörter,
Umgebungsvariablen oder Exceptiontexte werden dafür gelesen/ausgegeben.
Die vorhandene sanitierte Fehlerbehandlung und der Fail-fast-Launcher bleiben erhalten.
Vor der Fokus-Assertion wird zusätzlich `focus-cycle-<rolle>-<breite>.png` gespeichert.

## Tests und Einschränkungen

1. Neue Fokusregression zuerst: **10 pytest-Tests bestanden** (0,75 s), darunter
   ein Lauf mit **10 bestandenen JavaScript-Fällen** gegen den tatsächlichen
   `interface.js`-Code. Diagnosefälle führen auch den tatsächlichen JavaScript-
   Ausdruck aus; DOM-Doubles werfen bei Zugriff auf Werte, Text oder HTML.
2. Relevante Regressionen vor Commit: **133 bestanden**, eine bestehende
   Starlette/httpx-Deprecation-Warnung, 30,44 s. Keine Skips.
3. Wiederholung auf exakt **e1f262bbfe4ff4a039afa3a49aad995a5ac3efcf**:
   **133 bestanden**, gleiche Warnung, **30,07 s**, keine Skips.
   Nachweis: `.verification/filter-focus-e1f262b-a7ad1fc06691493b9820f2af1d8402d3/`.
   Enthält `source.txt`, `pytest.log`, `results.xml` und Artefakthashes.
4. Tatsächlicher integrierter Browseraufruf auf diesem Commit: **Exitcode 1**,
   `automation_driver_permission_denied`, `WinError 5` vor dem Browserstart.
   Zwei Fixture-/Serverchecks, keine Browserchecks. Toolbar/Excel nicht gestartet.
   Nachweis: `.verification/integrated-browsers-cad36536e1c2436aad060f4b50fa0861/`.
   **Keine neuen Screenshots oder Browser-Fokusmessungen erzeugt.**

Die erste Ausführung des neuen Node-Test-Harness mit separatem Worker scheiterte
hier an `spawn EPERM`. Der Harness führt `node:test` nun direkt im gestarteten
Node-Prozess mit festem TAP-Reporter aus. Kein Test wurde entfernt/übersprungen,
keine ACL oder Umgebungsschutzregel geändert. Ein anfänglicher Reporterformat-
Mismatch wurde ebenfalls im Harness korrigiert.

Ausgeführte pytest-Dateien: `test_filter_focus.py`, `test_contract_toolbar.py`,
`test_frontend_redesign.py`, `test_excel_selection.py`,
`test_integrated_browser_acceptance.py`, `test_browser_diagnostics.py`,
`test_toolbar_geometry.py`. DOM-Doubles ersetzen ausdrücklich nicht die native
Browserabnahme. Kein erneuter vollständiger PostgreSQL-Lauf: keine Backendänderung.
Vorherige PostgreSQL-Ergebnisse behalten ihre ursprüngliche Revisionsbindung.

## Vollständiger Windows-Aufruf

Unter dem normalen autorisierten Windows-Konto genau diesen Launcher ausführen:

```powershell
powershell.exe -NoProfile -File "C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-IntegratedBrowserVerification.ps1" -ExpectedSource e1f262bbfe4ff4a039afa3a49aad995a5ac3efcf -Channel msedge
```

Er startet Redesign, Toolbar und Excel sequenziell mit isolierten synthetischen
Daten, prüft Quellrevision und relevante Dateisauberkeit vor/nach jedem Kind,
bewahrt Exitcodes und Evidenz und stoppt beim ersten Fehler. `SUCCESS` setzt
alle drei erfolgreichen Suiten voraus. Dokumentationsänderungen sind zulässig.

Danach tatsächlich ansehen: `after-*`, `open-*`, `expanded-*`, `focus-cycle-*`
und Excel-Aufnahmen aller vier Breiten und Rollen. Die `focus_measurements` und
Geometriewerte für geschlossen/offen/erneut geschlossen prüfen. Erwartet sind
`reset → close → reset`, blockierter Hintergrundfokus, `Escape → toggle` und
Wiederöffnung mit `search`. Darstellungs-, Scroll-, Popover-, Tabellen-/Import-
und Tastaturabnahme erst anhand dieses neuen Laufs bestätigen.

**Browserabnahme offen. RELEASE READY: nein.** Alte 373 Checks und die geprüfte
alte 390px-Aufnahme sind kein Abnahmenachweis für den korrigierten Commit.

## Exakte Änderungen

Versioniert in e1f262b:

- `app/static/interface.js`
- `scripts/browser_focus.py`
- `scripts/verify_contract_toolbar.py`
- `tests/js/filter_dialog_focus.cjs`
- `tests/test_filter_focus.py`

Lokal ergänzte Berichte: `docs/FILTER_FOCUS_ACCEPTANCE.md`,
`docs/INTEGRATED_RELEASE.md`. Vorhandene lokale Änderungen und frühere Berichte
bleiben erhalten. Kein Push, Merge, Deployment, STRATO-/Produktionszugriff.
