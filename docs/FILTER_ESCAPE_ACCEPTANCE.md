# Escape-Abnahme: synchronisierte Prüfung des Filterdialogs

Stand: 23.10.2026. Kanonisches Projekt, `release/redesign-integration`.
Korrekturcommit: **461e030b015c37e47c6204a5b6c7cf6dc35cd61f**.
Nur Toolbar-Browserverifikation und zugehörige Tests geändert. Anwendung,
`app/static/interface.js`, CSS, Backend und Excel-Runner bleiben bytegleich.

## Bestätigte Ursache

Benutzerlauf auf `e163dd50efc61f87bd7ed6d1e4fa4a69f8626625`:
`.verification/toolbar-browser-64b37a37e69c4ce5b458e10ba49ba604/`.
43 Checks bestanden; `admin_escape_focus_768` ist danach fehlgeschlagen.
Die neuen Fokusmessungen belegen die tatsächlich fehlgeschlagene Teilbedingung:

| Phase | Tatsächlicher Fokus | Dialog offen | Nativ modal | aria-expanded |
|---|---|---|---|---|
| Direkt vor Escape (`admin_background_inert_768`) | Zurücksetzen | ja | ja | true |
| Snapshot nach Escape (`admin_escape_768`) | Suche & Filter | nein | nein | **true** |

`matches_expected=true`, `active_in_dialog=false`, `document_has_focus=true` und
`controls_dialog=true` waren nach Escape ebenfalls bereits korrekt.
**Es war kein Fokusverlust. Ausschließlich der zu früh gespeicherte Expanded-Zustand
ließ die zusammengesetzte Assertion fehlschlagen.** Der native Schließablauf hatte
den Dialog bereits geschlossen und den Fokus zum vorhandenen Trigger zurückgegeben.

`interface.js` aktualisiert `aria-expanded=false`, entfernt die Scrollsperre und
fokussiert den Trigger nochmals mit `preventScroll:true` im `close`-Eventhandler.
Dieses native Event wird nach dem eigentlichen Schließen abgearbeitet. Der Runner
las unmittelbar nach `keyboard.press('Escape')` einen Snapshot, ohne auf dieses
Cleanup zu warten, und verwendete dessen gespeicherten Expanded-Wert anschließend
in der Assertion. Ein späteres `dialog.is_visible()` aktualisiert den alten
Snapshot nicht. Dass der 390px-Lauf zuvor bestand, ist kein anderer Geschäftsfall,
sondern eine andere zeitliche Reihenfolge dieser asynchronen Aufgaben.

Der alte Lauf hat **keinen zusätzlichen Snapshot nach dem close-Handler** gespeichert.
Dieser historische Zustand wird nicht erfunden. Der tatsächliche Anwendungshandler
wurde nun im JavaScript-Test mit verzögert zugestelltem close-Event ausgeführt:
vor Eventzustellung entsteht genau der beobachtete Zwischenzustand; danach bleibt
der Fokus auf dem Trigger und Expanded/Scrollsperre sind bereinigt.

## DOM, Breakpoints und Sichtprüfung

Bei 768px ist der Filter bereits der schwebende modale Popover; das vollflächige
Drawer-CSS gilt bis 700px. Die Sidebar hat unabhängig davon einen Breakpoint von
1000px. Der Filter nutzt `showModal()` und native Hintergrund-Inertheit, keinen
manuellen Wechsel von `workspace.inert`. Der Sidebar-Escape-Handler greift nur bei
`nav-open`. Es gibt keinen Filter-Resize-Handler, der beim Schließen einen anderen
Fokus setzt, und keinen Formular-Neuaufbau in diesem Ablauf.

Die tatsächlich angesehene Aufnahme `toolbar/open-admin-768.png` zeigt den
Popover, den Trigger im Seitenkopf und die geschlossene mobile Sidebar. Die
gemessene Seitenbreite beträgt 768px, ohne Seitenoverflow. Der Trigger war nach
Escape nachweislich existent und fokussiert. Neue Messfelder prüfen zusätzlich
verbundenen DOM-Knoten, Sichtbarkeit, Enabled-/Tabindex-Zustand, Inertheit,
Navigation und Scrollsperre. Eine echte Aufnahme nach abgeschlossener Escape-
Behandlung wird beim nächsten Windows-Lauf erzeugt.

## Korrektur ohne abgeschwächte Assertions

- `escape_filter_and_wait` protokolliert den Zustand vor Escape und löst die
  echte Taste aus. `wait_filter_closed` protokolliert den unmittelbaren Zustand,
  wartet auf geschlossenes Dialogelement, `aria-expanded=false` und aufgehobene
  Filter-Scrollsperre, und erfasst anschließend zwei Fokuszustände: nach Cleanup
  und im folgenden Animation Frame.
- Gewartet wird **nicht** darauf, dass der Fokus irgendwann richtig wird.
  Beide anschließenden Snapshots müssen den richtigen Fokus, geschlossenen
  Dialog, korrekte ARIA-Verknüpfung und einen sichtbaren, aktivierten, nicht inerten,
  per Tab erreichbaren Trigger zeigen. Eine offene Navigation ist ebenfalls
  unzulässig. Ein echter Fokusfehler bleibt damit ein Assertionfehler.
- Keine Sleeps, keine Timeout-Erhöhung, kein erzwungener Fokus durch den Runner,
  keine Änderungen an Modalität, Escape, Tastatur-Umlauf oder Anwendungscode.
- Derselbe Abschluss wird für Außerklick und Schließen-Schaltfläche im Toolbar-
  Runner verwendet, da sie denselben nativen close-Handler auslösen.
- Die bestehenden Breiten 390/768/1280/1440 px und Rollen admin/kultur/pruefer
  werden weiter durchlaufen. `escape-<rolle>-<breite>.png` entsteht nach dem
  Schließablauf und vor der Assertion.

`focus_measurements` speichert `*_escape_*_before`, `*_escape_*_immediate`, den
bisherigen Basisnamen für den abgeschlossenen Zustand sowie `*_escape_*_frame`.
Gespeichert werden nur feste Elementkennungen und boolesche Zustände. Keine
Feldwerte, Zugangsdaten, MFA-Secrets, URLs oder Sessioninformationen.

## Ausgeführte Verifikation

- Zuerst Fokus-/Dismissal-Regressionsfälle: **29 bestanden**, 2,94 s.
- Anschließend Fokus-, Polling-, Geometrie-, Diagnose- und Launcher-Regressionsfälle:
  **141 bestanden**, 11,79 s.
- Auf exakt **461e030b015c37e47c6204a5b6c7cf6dc35cd61f**, zusätzlich mit
  HTTP-Vertragstoolbar-Regression: **146 bestanden, keine Skips**, 17,81 s.
  Eine bestehende Starlette/httpx-Deprecation-Warnung.

Nachweis: `.verification/filter-dismissal-461e030-98fec7b125a94e45a69aae2fd3f24fb5/`
mit SHA, JUnit, Log und Hashmanifest. Die neuen Tests führen den unveränderten
Anwendungs-Close-Handler bei allen vier Viewportbreiten im DOM-Double aus und
testen den tatsächlichen Wait-Ausdruck. Sie ersetzen keine native Browserabnahme.
Falscher Fokus, unsichtbarer/deaktivierter/inert gewordener Trigger, offene
Navigation und ausbleibendes Cleanup bleiben nachweislich Fehler.

Der neue Standalone-Toolbar-Aufruf wurde hier tatsächlich versucht:
**Exit 1, WinError 5**, `automation_driver_permission_denied`, vor Browserstart.
Evidenz: `.verification/toolbar-browser-e9b385e109fe494ea063f00f4d3c1e6d/`.
Keine neuen Screenshots oder nativen Fokusmessungen konnten erzeugt werden.

**Excel nicht erneut ausgeführt.** Der bestätigte Benutzerlauf
`.verification/excel-browser-43cef1bdbffc4cddb248b6a5f535fb92/` auf e163dd5 hat
**383 Checks bestanden, Exit 0**. Anwendung und Excel-Verifikationspfad wurden
seitdem nicht geändert; `browser_focus.py` wird ausschließlich vom Toolbar-Runner
verwendet. Der frühere Excel-Nachweis bleibt erhalten und an seine Revision gebunden.
Keine erneute vollständige PostgreSQL-Suite: keine Backendänderung.

## Einziger jetzt erforderlicher Windows-Aufruf

Unter dem normalen autorisierten Windows-Konto:

```powershell
powershell.exe -NoProfile -File "C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-TargetedBrowserVerification.ps1" -ExpectedSource 461e030b015c37e47c6204a5b6c7cf6dc35cd61f -Suite toolbar -Channel msedge
```

Der Launcher erstellt ein neues isoliertes Evidenzverzeichnis, prüft Revision
und unveränderte relevante Quellen und erhält den echten Exitcode. Danach
`sanitized-report.json`, `toolbar/result.json` und die tatsächlichen Escape-
Screenshots aller vier Breiten prüfen. Bei Fehlern zeigen die getrennten
Transitionszustände, welche Abschlussbedingung oder welches Fokusziel abwich.

**Toolbar-Browserabnahme weiterhin offen; RELEASE READY: nein.** Keine erneute
Excel-Ausführung und kein vollständiger integrierter Lauf wurden hier gestartet.

## Exakte Dateien

Versioniert in 461e030:

- `scripts/browser_focus.py`
- `scripts/verify_contract_toolbar.py`
- `tests/js/filter_dialog_focus.cjs`
- `tests/test_filter_focus.py`
- `tests/test_filter_dismissal.py`

Lokal ergänzte Dokumentation: `docs/FILTER_ESCAPE_ACCEPTANCE.md` und
`docs/INTEGRATED_RELEASE.md`. Vorherige lokale Änderungen und Evidenz bleiben
erhalten. Kein zusätzlicher Worktree, Push, Merge, Deployment oder STRATO-Zugriff.
