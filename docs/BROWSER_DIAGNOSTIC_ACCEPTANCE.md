# Browserdiagnose: Teilprüfungen und PostgreSQL-Abnahme

Stand: 22.10.2026. Kanonisches Projekt `OPEN_HERZ_Vertragsregister_Phase`,
Branch `release/redesign-integration`.

## Ursache und Korrektur

Ausgangsstand: `1d75ad99eb5a5711841d2c757590e01432a5f02a`. Der Benutzer meldete
für dessen PostgreSQL-Gesamtlauf 486 bestandene Tests, einen Fehler, zwei Skips
und 15 bestandene Untertests (695,89 s). Der Fehler war der fehlende
`check_count` bei `test_revision_runner_never_accepts_unverified_browser_child[child_assertion]`.
Diese Zahlen sind der vom Benutzer ausgeführte Lauf, kein neuer Agentenlauf.

Der alte Fehlerzweig konnte Teilprüfungen bereits übernehmen. Zuvor verwarf
`browser_result()` jedoch Ergebnisse, wenn deren `st_mtime` vor dem mit
`datetime.now(timezone.utc)` gemessenen Runnerstart lag. Beide Zeitquellen sind
unter Windows nicht gleich genau: Eine unmittelbar danach geschriebene Datei
kann einen minimal früheren Dateizeitstempel erhalten. Dann wurde ein gültiger
Assertion-Bericht als `browser_result_invalid` verworfen. Dieser Rückgabepfad
enthielt keinen `check_count`; daher der anschließende `KeyError` im Test.

Der zunächst unverändert ausgeführte Einzeltest bestand (0,07 s): Der Fehler
ist intermittierend. Eine separate lokale Probe mit 300 frisch geschriebenen
synthetischen Fehlerberichten reproduzierte 199 irrtümliche Ablehnungen.
Die negativen Zeitdifferenzen betrugen ungefähr 0,004 bis 0,906 ms.

Korrektur-Commit: `9b2df6c62a3bda23152a3dc30dacb49b2a2deee5`.

- Der Elternprozess erzeugt für jeden Browserlauf eine neue UUID-Kennung und
  übergibt sie über `--run-id`. Der Browserprozess gibt sie im strukturierten
  Ergebnis zurück. Die Kennung ist eine Laufzuordnung, kein Zugangstoken.
- Der Runner übernimmt ausschließlich Ergebnisse mit der passenden Kennung.
  Ein frischer Dateizeitstempel rettet keine fehlende oder wiederverwendete Kennung.
  Keine Zeit-Toleranz, kein Schlafen und keine pauschale Lockerung der Validierung.
- Aufrufer ohne Laufkennung behalten die bisherige strikte Zeitstempelprüfung.
  Source-SHA, Format, synthetischer Modus, eindeutige sichere Checknamen,
  Status-/Exitcode-Konsistenz und vollständige Erfolgsanforderungen bleiben erhalten.
- Verifizierbare Fehlerberichte behalten die tatsächliche Länge der geprüften
  Checkliste, den sicheren Checknamen und die erlaubten Diagnosefelder.
  Der Child-Exitcode bleibt ungleich null; der Runner meldet keinen Erfolg.
- Unverfügbare Prüfinformationen werden ausdrücklich als `null` ausgegeben.
  Es werden keine Checkzahlen erfunden, um einen Fehlerbericht vollständig aussehen
  zu lassen. `0` wird nur aus einer validierten leeren Checkliste abgeleitet.

## Schema und Schutz vor Datenabfluss

| Fall im Runner | check_count | failed_check | Ergebnis |
|---|---|---|---|
| Vollständig validierter Erfolg | Tatsächliche Listenlänge | null | VERIFIED, Fehlerfelder null |
| Validierter Assertion-Fehler | Tatsächliche Teilprüfungszahl | Sicherer Identifier, sofern vorhanden | IMPLEMENTED BUT UNVERIFIED; echte Fehlerkategorie/Stufe |
| Validierte Umgebungsblockade | Tatsächliche Teilprüfungszahl, ggf. 0 | Identifier oder null | IMPLEMENTED BUT UNVERIFIED; z. B. automation_driver_permission_denied |
| Fehlender, fremder, alter oder ungültiger Bericht | null | null | IMPLEMENTED BUT UNVERIFIED; feste Validierungsdiagnose |
| Source-Prüfung oder Prozessstart gescheitert | null | null | IMPLEMENTED BUT UNVERIFIED; executed=false |

Diagnosetexte entstehen ausschließlich aus dem festen lokalen Katalog. Freie
Child-Diagnosetexte, Exception-Inhalte, Umgebungsvariablen, Dateiinhalte und URLs
werden nicht übernommen. Checknamen müssen dem bestehenden Identifierformat
entsprechen; Exception-Typen und Stufen stammen aus erlaubten Mengen.
Windows-Fehlernummern müssen echte Integer sein, keine booleschen Werte.
Unbekannte zusätzliche JSON-Felder werden ignoriert. Rohes stdout/stderr bleibt
im privaten lokalen Log und gehört nicht in einen geteilten Bericht.

## Geänderte Dateien

- `scripts/browser_diagnostics.py`: Laufzuordnung, konsistente unbekannte Werte,
  weiterhin ausschließlich bereinigte Diagnoseinformationen.
- `scripts/run_pilot_verification.py`: Elternkennung, Übergabe und Validierung;
  unbekannte Teilprüfungsfelder auch bei frühem Abbruch.
- `scripts/verify_phase8_browser.py`: Validierung und Rückgabe der Elternkennung.
- `tests/test_browser_diagnostics.py`: deterministische Zeitversatz-Reproduktion,
  Assertions unverändert inhaltlich erhalten; 17 zusätzliche parametrisierte Fälle.
- Dieser Bericht und dessen Verweis im integrierten Release-Bericht.

Keine Änderungen an Anwendung, Geschäftsdaten, PostgreSQL-Installation,
Windows-ACLs, STRATO, Produktionskonfiguration oder bestehenden Prüfnachweisen.

## Tatsächliche Verifikation

1. Gezielter korrigierter Test: **1 bestanden**, 0,11 s, mit absichtlich um eine
   Sekunde zurückgesetztem Dateizeitstempel und echter Elternkennung im Testprotokoll.
2. Gesamte Browserdiagnostik: **43 bestanden**, 2,92 s, keine Skips;
   eine bestehende Starlette-Deprecation-Warnung.
3. Echter Runner-/Child-Aufruf am Korrektur-Commit: Die bestehende lokale
   Browserblockade bleibt sichtbar. Der bereinigte Bericht enthält nun
   `check_count: 2`, `exit_code: 1`, `failing_stage: automation_driver`,
   `error_code: automation_driver_permission_denied`, `winerror: 5` und
   `status: IMPLEMENTED BUT UNVERIFIED`. Keine Browserabnahme behauptet.
4. Vollständige PostgreSQL-Suite am Korrektur-Commit: **504 bestanden, kein Fehler,
   2 Skips und 15 bestandene Untertests**, **793,35 s**, eine bestehende
   Starlette-Deprecation-Warnung. Exitcode 0; Quellidentität vor und nach dem Lauf
   geprüft. Gegenüber dem gemeldeten Lauf: der zuvor fehlgeschlagene Test besteht,
   zusätzlich bestehen die 17 neuen Diagnosefälle.

Die zwei verbleibenden Skips sind `tests/test_phase5.py:192` (die Testidentität
darf keinen tatsächlichen Symlink erstellen) und `tests/test_phase5.py:341`
(echtes ClamAV nicht lokal konfiguriert). Keiner wird als Erfolg ausgewiesen;
keine neue PostgreSQL-spezifische Prüfung wurde übersprungen.

Der vorhandene Cluster wurde lesend als `127.0.0.1:55432`, Datenbank `postgres`,
Testrolle `ohvr_verify` (CREATEDB, kein Superuser/CREATEROLE/BYPASSRLS) bestätigt.
Verwendet wird ausschließlich die bestehende lokale Passdatei, ohne deren Inhalt
auszugeben. Die bestehenden Testfixtures erstellen und entfernen identifizierte
synthetische Datenbanken. Kein Clusterstart, keine Installation und keine ACL-Änderung.
Beobachtete Serverversion: 18.3; funktionale Tests schließen R43 nicht.

Lokale Originale unter `.verification/`:
`browser-diagnostic-repro.*`, `browser-diagnostic-fixed-target.*`,
`browser-diagnostic-fixed-all.*`, `browser-diagnostic-real-child/sanitized-report.json`,
`browser-diagnostic-postgresql-run.json`, `browser-diagnostic-postgresql-full.xml`
und `browser-diagnostic-postgresql-full.log`.
Die zusammengefassten Zahlen, Skip-Gründe und SHA-256-Hashes der Originalbelege
stehen in `.verification/browser-diagnostic-acceptance.json`. Die bestehenden
früheren Release-/Fehlerbelege bleiben unverändert erhalten.

**RELEASE READY bleibt ausdrücklich offen.** Neue Hosted-CI, tatsächliche
Browser-/visuelle Abnahme, native Sicherheitsbaseline, echter Scanner und die
separaten Betriebsfreigaben werden durch diesen Diagnosefix nicht ersetzt.
