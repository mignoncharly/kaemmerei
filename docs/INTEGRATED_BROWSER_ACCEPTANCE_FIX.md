# Integrierte Browserabnahme: Korrekturen vom 23.10.2026

Arbeitsort: `C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase`.
Branch: `release/redesign-integration`. Keine neue Arbeitskopie, kein Push, Merge
oder Deployment. Ausschließlich isolierte synthetische Daten.

## Quellstand und ursprüngliche Nachweise

Zu Beginn war der Arbeitsbaum sauber, HEAD war
`7097281c4f18734dcce67a58f0f2008478319fae`. Gegenüber dem zuvor mit PostgreSQL
geprüften `9b2df6c62a3bda23152a3dc30dacb49b2a2deee5` änderten sich ausschließlich
`docs/BROWSER_DIAGNOSTIC_ACCEPTANCE.md` und `docs/INTEGRATED_RELEASE.md`.
Es gab keine dazwischenliegenden Änderungen an Anwendung oder Browserprüfern.

Der neue **Code-Kandidat** ist
`d5f402d9f93d25231fb40aa843395da70f5267eb`.
Frühere U026-/PostgreSQL-Ergebnisse werden nicht auf diesen Kandidaten übertragen.

Die unveränderten Benutzerartefakte liegen unter `.verification/`:

| Lauf | Ergebnis auf 7097281 | Erhaltene Prüfungen |
|---|---|---:|
| `redesign-20261023-000024` | Fehler, fälschlich Phase `mfa` | 31 |
| `filter-20261023-000024` | `admin_reflow_390` fehlgeschlagen | 2 |
| `excel-20261023-000024` | `admin_reflow_390` fehlgeschlagen | 2 |

SHA-256 und PNG-Abmessungen aller ursprünglichen JSON-/Bildartefakte sind lokal
in `.verification/browser-failure-investigation/original-artifact-manifest.json`
festgehalten. Keine vorhandenen Nachweise wurden überschrieben.

## Fehler 1: ungültige Dokument-Fixture und veraltete Phasenangabe

Der Redesign-Bericht enthält bereits erfolgreiche MFA-Anmeldung, Enrollment und
Replay-Abwehr. Danach ruft der Runner `extended()` auf. Dieser Abschnitt legte
drei synthetische `ContractDocument`-Datensätze **ohne `storage_key` und ohne
`external_url`** an. Der Commit scheiterte an der unveränderten Datenbankregel
`document_exactly_one_source` aus `app/schema_rules.py`.

Die Exception wurde ohne Browser reproduziert: `IntegrityError` an diesem
Fixture-Commit. Es wurden nur Exception-Klasse und Constraint-Name ausgewertet,
keine SQL-Parameter, Credentials oder MFA-Geheimnisse ausgegeben. In den
Benutzerartefakten lag kein privater Traceback vor. Die Ursache wurde deshalb
durch direkte Ausführung der betroffenen Fixture bestätigt.

`extended()` hatte die vom vorherigen Szenario verbliebene Phase `mfa` nicht
zurückgesetzt. Die sichere Exception-Allowlist bildete `IntegrityError` außerdem
auf `Exception` ab. Zusammen entstand die irreführende MFA-Fehlermeldung.

Korrektur: gemeinsame, direkt testbare Fixture `seed_extended()` mit eindeutigem
synthetischem Storage-Key je Dokument. Es handelt sich bewusst nur um Metadaten
nicht freigegebener Dokumente; es gibt keine fingierte erfolgreiche Virenprüfung.
Die drei Zustände bleiben `pending`, `rejected`, `legacy_unverified`; alle direkten
Downloadversuche liefern weiterhin HTTP 409. Neue Abschnitte setzen ihre eigene
Phase (`dependencies`, `synthetic_fixture`, anschließend Browserphasen).

MFA-Code, Zeitfenster, Replay-Abwehr, Enrollment-Regeln, Sessionvalidierung und
Produktionskonfiguration wurden nicht geändert.

## Fehler 2 und 3: gemeinsamer Tabellen-Scrollbereich

Beide Prüfer verwenden unverändert die strenge Messung
`document.documentElement.scrollWidth <= innerWidth + 1`.
Der Fehler wurde nicht durch Abschwächen dieser Assertion behandelt.

Im Tabellenkopf liegt der für Screenreader benötigte Text „Aktionen“ als
absolut positioniertes `.visually-hidden`-Element in der letzten Spalte. Der
umgebende `.table-scroll` hatte zwar `overflow-x:auto`, aber keinen positionierten
Containing Block. Damit konnte das absolut positionierte Element außerhalb der
sichtbaren Tabellenbreite den Seiten-Scrollbereich vergrößern. Die gemeinsame
CSS-Regel betrifft beide fehlgeschlagenen Runner.

Korrektur: **`position:relative` am vorhandenen `.table-scroll`**. Der zugängliche
Spaltentitel bleibt erhalten und gehört nun zur scrollenden Tabelle. Kein
globales Abschneiden der Seite, keine Verschiebungen, keine geänderten Spalten,
keine Änderung an Import-/Exportregeln oder Sidebar.

Die vier vorhandenen Vorheraufnahmen wurden angesehen:

| Viewport | Tatsächliche PNG-Breite | Erste Zeile laut ursprünglichem Runner |
|---:|---:|---:|
| 390 | 816 | 1029,53 px |
| 768 | 884 | 862,36 px |
| 1280 | 1280 | 728,17 px |
| 1440 | 1440 | 714,20 px |

Diese Aufnahmen zeigen den vom Runner eingesetzten historischen Layoutvergleich
`a36fb93` mit derselben fehlenden Tabellenpositionierung. Sie sind **keine neuen
Nachheraufnahmen**. Für das aktuelle Layout belegen die ursprünglichen Berichte
die Reflow-Fehler; sie enthalten keine Elementmessungen. Die neue CSS-Korrektur
muss im autorisierten Benutzerbrowser erneut visuell bestätigt werden.

Alle drei Runner sichern jetzt numerische Layoutmessungen und bei Reflow-Fehlern
eine Aufnahme **vor** dem Abbruch. Erfasst werden feste Layoutselektoren, Breiten,
Positionen und Containing-Block-Zugehörigkeit, keine Feldinhalte oder DOM-Dumps.
Der Toolbar-Runner prüft zusätzlich den Bezugspunkt des unsichtbaren Tabellenkopfs
und die Seitenbreite bei horizontal gescrollter Tabelle. Der Excel-Runner prüft
auch den Zustand mit eingeblendeter Auswahlleiste. Bisherige Tastatur-, Fokus-,
Rollen-, Popover- und Importzentrierungsprüfungen bleiben erhalten.

## Gemeinsamer Windows-Prüflauf

`scripts/Invoke-IntegratedBrowserVerification.ps1` startet den getesteten
Python-Koordinator `scripts/verify_integrated_browsers.py`. Er führt Redesign,
Toolbar und Excel strikt nacheinander aus. Ein fehlgeschlagener Kindprozess
beendet den Lauf mit dessen exaktem Exitcode; ein ungültiger Bericht oder
Quellstandswechsel bei Exitcode 0 beendet ihn mit Exitcode 2.

Jeder Lauf erhält ein neues Verzeichnis `.verification/integrated-browsers-<UUID>`.
Jedes Kind erhält eine frische Run-ID; JSON-Format, SHA, Run-ID, synthetischer
Datenmodus, eindeutige Prüfnamen und erforderliche Abschlussprüfungen werden
validiert. Vor und nach jedem Kind werden HEAD und relevante unveränderte
Quelltexte geprüft. Nur drei valide Erfolge führen zu `SUCCESS`.

Private Kindprozess-Ausgaben bleiben in `*-private.log`; auf der Konsole werden
keine Ausnahmen, Credentials oder Sessiondaten ausgegeben. `sanitized-report.json`
enthält ausschließlich feste Diagnosefelder, echte validierte Teilprüfungszahlen,
Exitcodes und Ergebnishashes. Bilder und Einzelberichte bleiben in den drei
Unterverzeichnissen erhalten. Keine automatischen Installationen oder ACL-Änderungen.

Ein vollständiger Aufruf unter dem autorisierten Windows-Benutzerkonto:

```powershell
powershell.exe -NoProfile -File "C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-IntegratedBrowserVerification.ps1" -ExpectedSource d5f402d9f93d25231fb40aa843395da70f5267eb -Channel msedge
```

Bei einer späteren reinen Dokumentationsrevision muss die erwartete SHA genau
dieser Revision entsprechen; die Anwendung darf während des Laufs nicht geändert
werden. Es ist kein zusätzlicher manueller `SUCCESS`-Befehl erforderlich.

## Tatsächliche neue Verifikation

- Neue gezielte Tests zunächst: **14 bestanden**. Der erste Versuch mit Pytests
  `tmp_path` scheiterte an der bekannten privaten Windows-Temp-Verzeichnis-ACL.
  Die neuen Tests verwenden jetzt die bestehende `scratch_directory`-Infrastruktur;
  Windows-ACLs wurden nicht geändert.
- Bestehende Frontend-/Toolbar-/Excel-/MFA-/Security- und Diagnoseregressionen:
  **141 bestanden, 3 PostgreSQL-spezifische Skips**, 64,39 s. JUnit:
  `.verification/browser-fix-regressions.xml`.
- Nach Ergänzung der drei Abhängigkeiten-/Phasentests: **60 Diagnosetests bestanden**,
  5,84 s. JUnit: `.verification/browser-fix-diagnostics-final.xml`.
- Echter Aufruf des gemeinsamen PowerShell-Launchers auf `d5f402d`: **Exitcode 1**,
  `automation_driver_permission_denied`, Phase `automation_driver`, **WinError 5**.
  Zwei Teilprüfungen erhalten; Toolbar und Excel folgerichtig nicht gestartet.
  Kein `SUCCESS`, keine neue Browseraufnahme. Nachweis:
  `.verification/integrated-browsers-cf159367267a4184b5bf5cdf8ccc59dc/sanitized-report.json`.
- Vollständiger neuer PostgreSQL-Lauf auf `d5f402d`: **521 bestanden, 2 Skips,
  15 Untertests bestanden; 0 Fehler**, 975,79 s; Runner-Exitcode **0**, `VERIFIED`.
  Revisionsgebundener Runner, Ziel `127.0.0.1:55432`, PostgreSQL 18.3,
  eingeschränkte Rolle `ohvr_verify`, zufällige synthetische Datenbanken.
  Ausgabe: `.verification/browser-fix-postgresql-d5f402d/`.
  Quelle vor und nach dem Lauf unverändert bestätigt; Zeitfenster
  `2026-10-23T06:10:21Z` bis `2026-10-23T06:26:47Z`.
  JUnit-SHA-256:
  `817eb0036cc38c71cc995e4a5ef8a55d5b220a8c033a8251b5460a2367eaf987`.
  Die zwei Skips sind echte lokale Umgebungsgrenzen, keine bestandenen Tests:
  `test_actual_linked_storage_is_rejected` (OS verweigert Symlink-Erzeugung)
  und `test_real_clamav_engine_with_current_official_database`
  (echter ClamAV lokal nicht konfiguriert). Keine Änderungen an ACLs oder Scanner.

Die initialen gezielten Tests liefen auf dem anschließend als `d5f402d`
versionierten Arbeitsstand. Der gemeinsame Browseraufruf und die PostgreSQL-
Gesamtsuite sind direkt an diese SHA gebunden. Die drei zuvor unter SQLite
übersprungenen PostgreSQL-Prüfungen bestanden in der Gesamtsuite. Die Laufzeit
dieser Tests ist kein neuer Produktions-Performance- oder Hostingnachweis.

Die aktualisierten beiden Markdown-Berichte bleiben als lokale Änderungen im
Arbeitsbaum. HEAD und Anwendungscode bleiben dadurch genau auf der getesteten
SHA `d5f402d`; der oben angegebene Browseraufruf ist unverändert ausführbar.

## Dateien und verbleibende Gates

Code: `app/static/site.css`, `scripts/verify_frontend_redesign.py`,
`scripts/verify_contract_toolbar.py`, `scripts/verify_excel_selection.py`,
`scripts/browser_layout.py`, `scripts/verify_integrated_browsers.py`,
`scripts/Invoke-IntegratedBrowserVerification.ps1`,
`tests/test_integrated_browser_acceptance.py`.
Dokumentation: dieser Bericht und `docs/INTEGRATED_RELEASE.md`.

**INTEGRATED:** ja. **TESTED:** gezielte Regressionen und vollständige PostgreSQL-
Suite wie oben bestanden; Browser-/visuelle Abnahme noch offen.
**RELEASE READY:** nein. **DEPLOYED:** nein.
**DEPLOYMENT BLOCKED:** weiterhin keine freigegebene Serverumgebung.

Offen bleiben der Benutzer-Browserlauf und die Sichtprüfung der neuen Aufnahmen
bei 390/768/1280/1440 px, einschließlich Rollen admin/kultur/bau/pruefer, Navigation,
Popover, Tabellenposition, Auswahl, Importzentrierung und Fokus. Erst nach lokaler
Abnahme folgt der separat autorisierte finale CI-Schritt; jetzt kein Push/Merge.
Die echte Scanner-/Betriebsfreigabe wird durch synthetische Prüfungen nicht ersetzt.
