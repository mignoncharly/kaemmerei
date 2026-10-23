# Toolbar-Polling: Fehleranalyse, Korrektur und getrennte Browserprüfung

Stand 23.10.2026. Kanonisches Projekt, Branch `release/redesign-integration`.
Korrekturcommit: **e163dd50efc61f87bd7ed6d1e4fa4a69f8626625**.
Keine Anwendungs-, CSS-, Backend-, MFA-, Berechtigungs- oder Excel-Geschäftslogik geändert.

## Unveränderte ursprüngliche Evidenz

Benutzerlauf auf `e1f262bbfe4ff4a039afa3a49aad995a5ac3efcf`:
`.verification/integrated-browsers-fd66fa456b6d4aa79080a14ffa5c53c0/`.

- Redesign: **373 Checks bestanden**.
- Toolbar: **24 Checks bestanden**, anschließend `browser_execution_failed`,
  Stage `browser_scenarios`, Exceptionklasse `Error`, keine fehlgeschlagene Assertion.
- Excel: nicht gestartet, wie vom integrierten Fail-fast-Lauf vorgesehen.

`toolbar-private.log` besteht aus drei Zeilen: einer zweizeiligen
Starlette/httpx-Deprecation-Warnung und dem Ergebnis-JSON. Das JSON ist inhaltlich
identisch mit `toolbar/result.json`. **Weder Exceptiontext noch Stacktrace sind
enthalten.** Der damalige Handler fing die Exception ab und gab nur die Klasse aus.
Der genaue historische Exceptiontext kann deshalb nicht nachträglich ermittelt
werden. Eine angeblich aus diesem Log gelesene CSP-Exception oder geschlossene
Seite wäre eine unbelegte Behauptung.

Letzter erfolgreicher Check: **`admin_reset_all_390`**. Danach sind Fokus auf den
Tabellen-Scrollbereich und `admin_before_table_scroll_390` noch ausgeführt worden.
Messwerte: Seite 390 px breit, lokaler Tabellencontainer 324 px, Tabelleninhalt
910 px, horizontaler Tabellen-Scrollwert 0, Seiten-Y 151, erste Zeile im Dokument
bei 660,203125 und im Viewport bei 509,203125 px. Kein gemessener Seitenoverflow.

Die anschließende Reihenfolge im getesteten Quellstand war:

1. `region.evaluate('(e)=>e.scrollWidth>e.clientWidth+1')`.
2. `page.keyboard.press('ArrowRight')`, falls scrollbar.
3. `page.wait_for_function('document.querySelector(".table-scroll").scrollLeft>0')`.
4. Scrollwert erneut lesen und `admin_table_keyboard_scroll_390` prüfen.

Dieser nächste Check wurde nicht erreicht. Die alte Evidenz grenzt den Fehler auf
dieses Intervall ein, identifiziert aber nicht dessen einzelne Operation. Es gibt
keinen aufgezeichneten Beleg für Navigation, geschlossene Seite, abgelöstes Element
oder Timeout. Ein Timeout hätte der vorhandene Handler gesondert klassifiziert.

Die frühere Fokuskorrektur hat ausdrücklich bestanden: `reset → close`, auch im
nächsten Frame, `close → reset`, Hintergrundfokus abgewehrt, Escape und Wiederöffnung.
Die tatsächlich betrachtete Aufnahme `toolbar/focus-cycle-admin-390.png` zeigt
den sichtbaren Fokusrahmen auf **Schließen**. Auch die Overlay-Geometrieprüfungen
haben bestanden. Diese Fehler werden nicht erneut aufgerollt.

## Reproduzierbarer Automationsfehler und Grenze des Nachweises

Der installierte Playwright-Code (`coreBundle.js`, Paketversion
`1.64.0-beta-1791568591000`) verwendet in `waitForFunctionExpression` zunächst
`globalThis.eval(expression)`. Ein Funktionsresultat wird gecacht; ein bloßes
boolesches Ausdrucksresultat wird beim nächsten Poll erneut per `eval` berechnet.
Bei einem zunächst falschen Scroll-Prädikat erfolgt dieser zweite Aufruf in einem
späteren Animation Frame. Das ist mit der bestehenden CSP ohne `unsafe-eval`
unverträglich. Ein sofort wahrer Fokus-Poll benötigt diesen zweiten Aufruf nicht.

Mit dem **aus der installierten Datei extrahierten tatsächlichen Predicate-Code**
wurde der Ablauf unter einer simulierten strengen Eval-Policy ausgeführt:

| Übergabe | Erster Poll | Zweiter Poll | Eval-Aufrufe |
|---|---|---|---|
| Bloßer Ausdruck | false | EvalError | 2 |
| Funktionsprädikat | false | true | 1 |

Experiment und Ergebnis:
`.verification/browser-polling-e6db2717814145b98b2411cf6aed1057/poll-installed.cjs`
und `poll-installed.json`. SHA-256 der untersuchten Bundle-Datei:
`829521b67ed7be90c7d6d6098ff39f2241562d47e4ad7ccab13710924a56001d`.
Das ist ein reproduzierbarer Fehler der Runner-Aufrufform, **kein neuer Browserlauf**.
Er erklärt das beobachtete Abbruchintervall schlüssig. Ob genau diese Exception
im ursprünglichen Windows-Lauf auftrat, bleibt ohne dessen verworfenen Stacktext
eine begründete Ursacheninferenz und muss im neuen Lauf bestätigt werden.

Korrektur: Die beiden `wait_for_function`-Aufrufe für Fokus und Scrollen erhalten
jetzt `() => ...`. Damit wird die Funktion einmal erzeugt und anschließend
aufgerufen. Weder CSP noch Browser-Sicherheitsoptionen oder Timeout wurden
verändert. ArrowRight bleibt eine echte Tastaturaktion; Scrollen wird nicht für
die Keyboard-Assertion künstlich gesetzt. Die bestehenden Assertions bleiben erhalten.

## Sichere Diagnose und separate Prüfläufe

- `last_completed_check` wird aus den bereits aufgezeichneten Checks abgeleitet.
- Beim Scrolltest wird `failed_operation` mit festem Namen gespeichert, etwa
  `table_press_arrow_right` oder `table_wait_scroll`.
- `page_closed_at_failure` wird vor dem normalen Context-Teardown erfasst.
- `source_frames` enthält ausschließlich erlaubte relative Runner-Dateien und
  Zeilennummern; keine Quellzeilen, Locals, absoluten Pfade oder Stack-Strings.
- `browser_error_kind` klassifiziert bekannte Meldungssignaturen in feste Werte
  wie `csp_eval_blocked`, `target_closed`, `execution_context_destroyed`,
  `element_detached`, `strict_mode_violation`, `timeout`, `unclassified`.
  Exceptiontexte selbst werden nicht ausgegeben. Unbekannte Fehler bleiben Fehler.
- Toolbar und Excel verwenden diese Diagnostik. Der Parent übernimmt nur
  erlaubte Felder/Werte und leitet den letzten Check selbst aus validierten Checks ab.
- Einzelläufe nutzen denselben revisions-/noncegebundenen Validator. Leere oder
  unerlaubte Suite-Auswahl wird abgewiesen. Ein Einzelerfolg heißt ausdrücklich
  `SUCCESS: selected browser suite only` und ist keine integrierte Abnahme.

## Tatsächlich ausgeführte Tests

1. Erste neue Pollingregression: **16 bestanden** (0,38 s).
2. Erweiterte Polling-/Diagnose-/Launcherprüfung: **42 bestanden** (3,15 s).
3. Relevante Gesamtregression vor Commit: **158 bestanden** (31,04 s).
4. Dieselbe Regression auf exakt **e163dd50efc61f87bd7ed6d1e4fa4a69f8626625**:
   **158 bestanden, keine Skips**, 30,66 s. Eine bestehende
   Starlette/httpx-Deprecation-Warnung.

Getestete Dateien: `test_browser_polling.py`, `test_filter_focus.py`,
`test_contract_toolbar.py`, `test_frontend_redesign.py`, `test_excel_selection.py`,
`test_integrated_browser_acceptance.py`, `test_browser_diagnostics.py`,
`test_toolbar_geometry.py`. Die neuen Fälle prüfen auch dauerhaft falsche Polls,
unveränderte Fehlerweitergabe, geschlossene Seiten, sanitierte Reports sowie
unabhängige Toolbar-/Excel-Ausführung mit exaktem Exitcode.

Revisionsgebundene Ergebnisse, JUnit, Log und Hashmanifest:
`.verification/browser-polling-e163dd5-063197431c2e4c37a8a2fc98a7c12931/`.
Keine vollständige PostgreSQL-Wiederholung, da keine relevante Backendänderung.

Beide Browser-Suiten wurden auf der neuen Revision **getrennt tatsächlich versucht**:

| Suite | Ergebnis hier | Evidenz unter `.verification/` |
|---|---|---|
| Toolbar | Exit 1; WinError 5 vor Browserstart | `toolbar-browser-e3c0748e39da44f9a9de902aea536e92/` |
| Excel | Exit 1; WinError 5 vor Browserstart | `excel-browser-66b7df0bb98449ee933c59a11c76256d/` |

Jeweils `automation_driver_permission_denied`, letzter Check `server_started`.
Excel wurde unabhängig vom Toolbar-Ergebnis gestartet. Keine neuen Browserchecks,
Fokus-/Layoutmessungen oder Screenshots entstanden. Vorherige Aufnahmen bleiben
unverändert erhalten. Keine ACL-/Installations-/Produktionsänderungen.

## Jetzt unter dem normalen Windows-Konto ausführen

Toolbar als eigenständiger Lauf:

```powershell
powershell.exe -NoProfile -File "C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-TargetedBrowserVerification.ps1" -ExpectedSource e163dd50efc61f87bd7ed6d1e4fa4a69f8626625 -Suite toolbar -Channel msedge
```

Excel separat ausführen, auch falls Toolbar noch fehlschlägt:

```powershell
powershell.exe -NoProfile -File "C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-TargetedBrowserVerification.ps1" -ExpectedSource e163dd50efc61f87bd7ed6d1e4fa4a69f8626625 -Suite excel -Channel msedge
```

Jeder Aufruf erzeugt ein neues isoliertes Verzeichnis, bindet Ergebnisse an diese
Revision, prüft unveränderte Quellen und erhält den echten Exitcode. Die beiden
Aufrufe sind absichtlich unabhängig; danach steht kein pauschaler Erfolgsbefehl.
Jeweils `sanitized-report.json` und gegebenenfalls `toolbar/result.json` bzw.
`excel/result.json` sowie tatsächliche Screenshots prüfen. Toolbar deckt admin,
kultur und pruefer ab; Excel zusätzlich bau, jeweils bei 390/768/1280/1440 px.
Die frühere Fokusnotiz bezeichnete bau irrtümlich auch als Toolbar-Testrolle;
der tatsächliche Toolbar-Rollenloop ist unverändert dreiteilig.

**Erst nach beiden erfolgreichen Einzelläufen** folgt erneut die vollständige
integrierte Abnahme aller drei Suiten auf derselben Revision samt Sichtprüfung.
Der endgültige integrierte Aufruf wird jetzt nicht als nächster Schritt ausgegeben.
**Browserabnahme offen; RELEASE READY: nein.** Die 373 bisherigen Redesignchecks
bleiben gültige Evidenz für e1f262b, nicht für einen neuen integrierten Browserlauf.

## Exakte Änderungen

Versioniert in e163dd5:

- `scripts/browser_layout.py`
- `scripts/browser_diagnostics.py`
- `scripts/verify_contract_toolbar.py`
- `scripts/verify_excel_selection.py` (nur Fehlerdiagnose)
- `scripts/verify_integrated_browsers.py`
- `scripts/Invoke-TargetedBrowserVerification.ps1`
- `tests/test_browser_polling.py`
- `tests/js/poll_predicate.cjs`
- `tests/test_integrated_browser_acceptance.py`

Lokal ergänzte Dokumentation: `docs/TOOLBAR_POLLING_ACCEPTANCE.md` und
`docs/INTEGRATED_RELEASE.md`. Alle vorherigen lokalen Dokumentationsänderungen
bleiben erhalten. Kein Push, Merge, Deployment oder STRATO-Zugriff.
