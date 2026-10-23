# Integrierte Hauptanwendung und Release-Status

Stand: 23.10.2026. Ausschließlich synthetische lokale Tests.

Verbindlicher Abschluss: [Konsolidierte Release-Abnahme und einziges weiteres Verfahren](FINAL_RELEASE_ACCEPTANCE.md).
Frühere Debuggingaufforderungen sind damit abgelöst; keine erneuten lokalen Einzelläufe erforderlich.
Vorherige Fortsetzung: [Escape-Abnahme und synchronisierter Dialogabschluss](FILTER_ESCAPE_ACCEPTANCE.md).
Vorherige Fortsetzung: [Toolbar-Polling und getrennte Browserprüfung](TOOLBAR_POLLING_ACCEPTANCE.md).
Vorherige Fortsetzung: [Filterdialog-Fokus und Browserabnahme](FILTER_FOCUS_ACCEPTANCE.md).
Vorherige Fortsetzung: [Toolbar-Overlay und korrigierter Browservergleich](TOOLBAR_OVERLAY_ACCEPTANCE.md).
Vorherige Fortsetzung: [Korrekturen der integrierten Browserabnahme](INTEGRATED_BROWSER_ACCEPTANCE_FIX.md).
Vorherige Fortsetzung: [Browserdiagnose-Korrektur und PostgreSQL-Nachprüfung](BROWSER_DIAGNOSTIC_ACCEPTANCE.md).
Die folgenden Integrationsnachweise bleiben an ihre ursprünglichen Commits gebunden.

## Verbindlicher Arbeitsort

Künftige Entwicklung erfolgt ausschließlich in
`C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase` auf dem integrierten
Kandidatenzweig `release/redesign-integration`, anschließend nach erfolgreicher
Verifikation und Prüfung des tatsächlichen Branchschutzes im vorgesehenen Hauptbranch.

Der Benutzer hat den bisherigen Redesign-Stand manuell geprüft und akzeptiert.
Dies ersetzt weder neue CI noch die technische Browser-/Betriebsabnahme des
integrierten Releases. Ein externer Zielserver ist ausdrücklich **nicht freigegeben**.

| Status | Tatsächlicher Stand |
|---|---|
| INTEGRATED | Ja, vollständige Historie im kanonischen Projekt zusammengeführt. |
| TESTED | PostgreSQL auf d5f402d: 521 bestanden, 2 Skips, 15 Untertests. Frontend auf e1f262b: 373 Checks. Excel auf e163dd5: 383 Checks. Toolbar auf 461e030: 356 Checks, Exit 0; dort außerdem 146 gezielte Regressionen. Scope-Abgleich und repräsentative Sichtprüfung dokumentiert. Keine erfundene gemeinsame Prüfrevision. |
| REVIEW PREPARED | Ja, Toolbar eingefroren; Evidenzmanifest, PR-Text und konsolidiertes Abschlussverfahren vorbereitet. |
| RELEASE READY | Nein: finale Hosted-CI und geltendes Repository-Review/Branchschutz noch ausstehend; GitHub hier nicht erreichbar. Keine neue lokale Browserrunde erforderlich. |
| DEPLOYED | Nein. Kein externes System verändert. |
| DEPLOYMENT BLOCKED | Kein identifizierter/freigegebener Windows/PostgreSQL/TLS-Zielserver. |

## Historie und Erhaltung

- Gemeinsame Basis: `3d4a180297db801293e4b86e42e9f60a55fbca86` (U026).
- Vollständiger Redesign-Endstand: `d15b4732a7e140bfba27904c31cd5c70cea368e2`,
  einschließlich Bulk-Export und letzter Zentrierungskorrektur.
- Kanonische lokale Änderungen zuerst bytegenau gesichert und mit `3cb6de8`
  versioniert: 30 geänderte/neue Dateien, einschließlich Dokumentation,
  STRATO-Bewertungen, Nachweisen, Haushaltszuordnung und `Start-TestDatabase.ps1`.
- Historienerhaltender Merge: `c193c9e`. Ein Konflikt im Vertragsformular:
  Haushaltsauswahl samt Altdaten-Fallback und neue Feldgruppen gemeinsam erhalten.
  Der fertige Merge-Baum entsprach vollständig dem Redesign-Endstand.
- `91b34966781dc19e6bf12790ae2a35b1a955a7f6` ergänzt die CI um Redesign-,
  Popover- und Excel-Browserprüfungen einschließlich Screenshot-Artefakten.
- Lokal vorhandenes `main`: `223eec99bcfaafdece2d2501c4866c0cfdbdfc56`,
  Vorfahr der Integration, ohne exklusiven lokalen Gegenstand.
  `origin/main` ist nur ein veralteter lokaler Trackingstand. Remote-Branch,
  Default-Branch und Schutzregeln konnten wegen Netzwerkfehler nicht neu bestätigt
  werden. Deshalb keine Änderung an `main` und kein Umgehen von Schutzregeln.

Die Sicherungen liegen ausschließlich lokal unter
`.verification/consolidation-preservation/`. Das vollständige Alt-Worktree-Archiv
enthält 831 einzeln geprüfte Dateien; SHA-256:
`e4de86f9292f806d65843e9284d71a5b411afbecb7fe7ba805a70f2444e89345`.
`RECOVERY-MANIFEST.json` im ZIP enthält die einzelnen Dateihashes.
Archiv: `retired-redesign-worktree.zip`. Separate Sicherungen der kanonischen
Änderungen und der vier unversionierten Referenzbilder bleiben ebenfalls erhalten.
Diese privaten Sicherungen nicht als CI-Artefakte oder ins Repository hochladen.

Git hat den Redesign-Worktree abgemeldet; nur das Hauptprojekt bleibt registriert.
Die branchgebundene Historie bleibt als Wiederherstellungspunkt erhalten.
Git konnte das Altverzeichnis nicht vollständig löschen. Die anschließende
native Löschung wurde von der automatischen Freigabeprüfung blockiert
(`sandbox_approval` nicht zulässig). Es verbleibt ein **inaktives Restverzeichnis**,
kein separater Entwicklungs-Worktree. Es darf nicht erneut als Projekt genutzt
werden. Eine spätere lokale Bereinigung darf erst nach erneuter Prüfung des
Archivhashes und der verbliebenen Dateien erfolgen. Keine Prüfbelege gehen verloren.

## Umfang und Datenbank

Alle Redesign-Commits sind Vorfahren des Kandidaten: gemeinsames Layout,
rollengebundene Navigation, Authentifizierung/MFA, Administration, Verträge,
Dokumente, Prüfungen, Filterdialog, Excel-Auswahl und Import, Status-/Fehlerseiten,
Assets, Browserprüfer und Berichte. Das Original wird nicht durch Verzeichniskopien
ersetzt. Bestehende API-Verträge bleiben erhalten; zusätzliche UI-Endpunkte sind
`GET /dashboard` und `POST /contracts/export-selected.xlsx`.

Keine Änderungen an der Alembic-Historie gegenüber U026. Einziger Schema-Head:
`0027_child_read_admission`. Sicherheits-/Workflow-/Dokument-Kernmodule bleiben
gegenüber U026 unverändert. Die neue Exportprüfung ist serverseitig, atomar in der
Zulässigkeitsentscheidung, CSRF-geschützt und auf 5.000 IDs begrenzt; das bestehende
XLSX-Schreibformat verhindert Formelausführung. Keine Dokumentanhänge im Export.
R01, R04 und R10 bleiben in `tests/test_phase1.py` als normale Regressionen enthalten.

## Ausgeführte Verifikation und genaue Grenzen

- Integrierte SQLite-Gesamtsuite: **453 bestanden, 36 Skips, 15 Untertests bestanden**,
  197,90 s, 13 Warnungen. Keine Fehler. Beginn am Merge-Stand `c193c9e`, während
  des Laufs ausschließlich CI-Konfiguration ergänzt; Anwendung unverändert.
  `.verification/integrated-sqlite.xml` und `.log` bewahren das Originalergebnis.
- Separate Phase-1-Verifikation: **22 Tests bestanden**, 14,04 s.
  `.verification/integrated-phase1.log`.
- Skips: 34 benötigen echtes PostgreSQL, einer echtes ClamAV, einer die unter
  dieser Identität gesperrte Symlink-Erstellung. Das sind **keine bestandenen Gates**.
- PostgreSQL-Start scheiterte vor der Suite an erforderlichen Owner-only-ACLs
  für das isolierte Testverzeichnis. Keine neue Zugangsdaten geschrieben,
  keine bestehende Windows-Datenbankdienst-Konfiguration geändert.
- Native Prüfung: lokale Clients/PostgreSQL-Binärdatei 18.3, geladenes libpq 18.4;
  tatsächlicher Server nicht abgefragt. R43-Baseline nicht bestanden. Keine
  Installation oder Sicherheitsabsenkung. `.verification/integrated-native-gate.json`.
- Echter Scanner: freigegebene Engine/Definitionen nicht konfiguriert;
  `.verification/integrated-scanner-gate.json` meldet EXTERNALLY_BLOCKED.
- Integrierte synthetische Browser-Server gestartet, aber Automationstreiber
  durch Windows `WinError 5` blockiert. Keine neuen Screenshots und keine
  behauptete visuelle Abnahme. Ergebnisse in `integrated-redesign-browser/` und
  `integrated-excel-browser/` unter `.verification/`.
- Zwei bytegleiche Pakete am Stand `91b3496` gebaut und vollständig verifiziert;
  isolierter Paketstart samt In-Memory-SQLite-Migration bestanden, 133 Dateien.
  Paket-SHA-256: `e9529ed0ee5543cb64f210f8673f512b84d2ca7008246281332089fd768eb7da`.
  `.verification/integrated-release/release-summary.json` enthält die Quellbindung.

Nach dieser Dokumentation wird der endgültige Kandidat erneut mit der kompletten
SQLite-Suite geprüft und als Paket gebaut. Die maschinenlesbare, genaue SHA-,
Test- und Artefaktzuordnung steht anschließend in
`.verification/integrated-final-evidence.json`; zugehörige Logs tragen `integrated-final`.
Dieses Dokument darf offene PostgreSQL-/Browser-/CI-Gates nicht durch ältere
U026-Ergebnisse ersetzen.

## Lokale Prüfung unter autorisiertem Windows-Konto

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
$releaseRun = Get-Date -Format 'yyyyMMdd-HHmmss'
$releaseSource = git rev-parse HEAD
python -m pytest -q --database sqlite --junitxml=".verification\sqlite-$releaseRun.xml"
& .\scripts\Start-TestDatabase.ps1
# Nur nach erfolgreichem Start des markierten, isolierten Testclusters:
python scripts\verify_phase1.py --database postgresql
python -m pytest -q --database postgresql --junitxml=".verification\postgresql-$releaseRun.xml"
python scripts\verify_frontend_redesign.py --channel msedge --output ".verification\redesign-$releaseRun"
python scripts\verify_contract_toolbar.py --channel msedge --output ".verification\filter-$releaseRun"
python scripts\verify_excel_selection.py --channel msedge --output ".verification\excel-$releaseRun"
git rev-parse HEAD  # Muss weiterhin $releaseSource entsprechen.
```

Browserabhängigkeiten: `requirements-browser.txt` und vorhandenes Edge. Alle drei
Prüfer starten eigene synthetische Anwendungen; keine Ziel-URL oder realen Daten.
Screenshots bei 390/768/1280/1440 px ansehen, Rollen admin/kultur/bau/pruefer prüfen.
Bei einem Fehler nicht Erfolg attestieren; `result.json` und originale Logs erhalten.
Für eine interaktive Vorschau: `python scripts\preview_frontend.py --port 8793`.
Diese nutzt ausschließlich temporäre SQLite-Daten und synthetische Testkonten;
sie ist kein PostgreSQL-/Scanner-/Produktionsnachweis.

## Final-source GitHub CI und Hauptbranch

Aktuelle Anweisung vom 23.10.2026: **kein Push oder Merge**. Zuerst vollständige
lokale Abnahme des neuen Kandidaten einschließlich Benutzer-Browserlauf.
Die nachfolgenden Angaben beschreiben den früher vorbereiteten Workflow und
keine jetzt ausgeführte oder freigegebene Veröffentlichung.

Fetch, API-Lesezugriffe und Push des Kandidaten wurden versucht, scheiterten aber
am konfigurierten Netzwerkpfad (GitHub:443 über nicht erreichbaren lokalen Proxy).
Kein neuer Workflow gestartet; keine neue Run-URL, Job-Ergebnisse oder Hosted-
Artefakthashes vorhanden. U026s zehn erfolgreiche Jobs gelten nur für U026.
GitHub CLI ist hier nicht installiert. Keine Credentials ausgelesen oder verändert.

Nach Wiederherstellung des autorisierten Zugangs: `git fetch origin`, aktuellen
Default-/Produktionsbranch, `main`-Schutzregeln, Rulesets und neue Commits prüfen.
Neue Gegenstände kontrolliert zusammenführen und erneut testen. Kandidaten mit
`git push -u origin release/redesign-integration` veröffentlichen, ohne Force.
Der bestehende Push-Workflow startet alle zehn Job-Ausführungen. Er enthält keine
Deployment-Aktion. Vollständige Historie wird für den Popover-Vorhervergleich geladen.
Exakte Head-SHA, Run-URL, jeden Job, JUnit-Zahlen/Skips sowie alle heruntergeladenen
Artefakte mit SHA-256 erhalten; keine Secrets oder private Recovery-Archive hochladen.
Erst nach grüner neuer CI, Browserabnahme und geltendem Reviewverfahren in den
bestätigten Hauptbranch übernehmen. Bei neuem Merge-Commit dessen CI ebenfalls
abwarten. Niemals einen ungeprüften Stand nur zum Auslösen von Deployment mergen.

## Deployment- und Rückrollstatus

Der Benutzer bestätigt: keine Serverzuordnung, keine Betriebsfreigabe, keine
Autorisierung echter kommunaler Daten. STRATO belegt nur SSH/SFTP, keine passende
Windows-/Service-/PostgreSQL-/TLS-Umgebung. Keine erneute STRATO-Verbindung,
keine Übertragung, keine Produktionsmigration, kein Service-Neustart.

Vor Deployment sind tatsächlicher Host/OS/Administrationsrechte, R43-konforme
Server und Clients, TLS/vertrauenswürdiger Proxy, internes/VPN-Netz, private
Dokumentablage/ACLs, freigegebener Scanner, Worker/Tasks, Geheimnisverwaltung,
Logs/Monitoring und Verantwortlichkeiten nachzuweisen. Zusätzlich konsistente
verschlüsselte DB-/Dokument-Sicherung, verifizierte Wiederherstellung auf neuem
isolierten Ziel, Source-/Konfigurationshash und genehmigtes Routing-/Rollbackverfahren.
Vorhandene Vorlagen sind kein Nachweis dieser Fähigkeiten.

Der bestehende [Release-Runbook](RELEASE_RUNBOOK.md) bleibt für technische Gates
maßgeblich; frühere pauschale Nichtautorisierungsangaben darin sind historisch.
Aktuell sind Integration/Tests/Release-Vorbereitung und geschützte Veröffentlichung
autorisiert, externes Deployment dagegen ausdrücklich gesperrt.
Da kein Deployment erfolgt ist, gibt es keinen ausgeführten Produktionsrollback.
U026 und der gesamte Redesign-Verlauf bleiben unverändert erreichbar; keine
Schema-Downgrades, kein Ersetzen echter Daten durch Vorschau-SQLite.
