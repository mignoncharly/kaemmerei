# GitHub-Abschluss: eine Veröffentlichung und Abnahme

Stand 23.10.2026. Die Veröffentlichung des integrierten Kandidaten, PR-Erstellung
und regelkonforme Integration nach erfolgreicher CI und erforderlichen Reviews
sind ausdrücklich freigegeben. Kein Deployment ist enthalten.

Fortschreibung: PR #1 wurde inzwischen unter dem autorisierten Windows-Konto
erstellt. Die zehn Jobs des erhaltenen Push-Laufs auf `7ba43ff` sind erfolgreich.
Die plattformspezifische Korrektur des lokalen Artefakt-Gates und die genaue
Evidenzzuordnung stehen in [RELEASE_PLATFORM_SKIP_CORRECTION.md](RELEASE_PLATFORM_SKIP_CORRECTION.md).
Zum Aktualisieren dieses bestehenden PRs wird derselbe Launcher mit
`-PullRequest 1` und der neuen vollständigen Kandidaten-SHA verwendet.

## Tatsächlicher Stand

Ausgangspunkt: `d44f6c9f435d07e5b6720c8ff8c2fd1790528c5f`, sauberes Arbeitsverzeichnis
auf `release/redesign-integration`. Der erneute lesende Remotezugriff scheiterte:
GitHub:443 ist über den konfigurierten lokalen Netzwerkpfad nicht erreichbar.
Kein Proxy, Token, ACL oder Remote wurde geändert. Deshalb gibt es aus dieser
Ausführung **keinen neuen PR, CI-Lauf, Review oder Merge**.

Ergänzt wurden ausschließlich Release-Launcher, dessen isolierte Tests und
Dokumentation. Anwendung, Browserprüfer, CI-Workflow, Abhängigkeiten und Datenbank
bleiben eingefroren. Die lokale Abnahme wird nicht wiederholt. Der neue Commit
enthält die Automatisierung und wird selbst Bestandteil des GitHub-Kandidaten.
Er ersetzt nicht die exakten bisherigen Prüfrevisionen in
[FINAL_RELEASE_ACCEPTANCE.md](FINAL_RELEASE_ACCEPTANCE.md).

## Einmaliger Windows-Aufruf

Aus der normalen, bereits für GitHub autorisierten Windows-Sitzung:

```powershell
& 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase\scripts\Invoke-GitHubReleaseAcceptance.ps1' -ExpectedSource '<vollständige SHA des neuen Launcher-Commits>'
```

Die konkrete SHA steht in der Übergabeantwort. Der Parameter ist fest; ein
ungeprüfter zukünftiger HEAD wird nicht automatisch übernommen. Voraussetzungen:
vorhandenes Python/Git und bestehende GitHub-Anmeldung über Git Credential Manager,
`gh auth` oder vorhandenes `GH_TOKEN`/`GITHUB_TOKEN`. Keine Zugangsdaten in den
Aufruf, Dokumente oder Chat schreiben. Die Anmeldung muss Repository/PR/Actions
und Branchschutz/Rulesets lesen sowie den freigegebenen Ablauf ausführen dürfen.
Fehlende API-Rechte werden nicht als fehlender Schutz interpretiert.

Der Aufruf wartet bis zu 24 Stunden auf CI und unabhängige Reviews. Währenddessen
kann der Reviewer den ausgegebenen PR in GitHub prüfen. Er benötigt mindestens
Schreibrechte. Autor-Selbstfreigaben, Bot-Reviews, veraltete/zurückgezogene
Freigaben zählen nicht. Alle zusätzlich verlangten Repository-Reviews und Checks
müssen erfüllt sein. Es gibt keine automatische Review-Freigabe.

## Ablauf und Abbruchbedingungen

1. Prüft sauberen kanonischen Quellstand, origin/push-URL, Abstammung und die auf
   Release-Automatisierung/Dokumentation begrenzten Änderungen seit der lokalen
   Abnahme. Lokale Änderungen führen zum Abbruch, niemals zu Reset/Clean.
2. Liest Defaultbranch, klassischen Branchschutz, effektive Regeln und geerbte
   Rulesets. Erwartet den dokumentierten Zielbranch `main`. Remote-Vorsprung
   verlangt eine bewusste Konflikt-/Scopeprüfung.
3. Veröffentlicht ohne Force-Push nach `review/integrated-release-<SHA12>`.
   Ein vorhandener Branch darf nur dieselbe SHA enthalten. Erstellt einen PR
   mit dem vorbereiteten Text und revisionsfesten Dokumentationslinks.
4. Wartet auf den bestehenden Workflow für Push und PR. Kein erneutes Dispatch
   eines erfolgreichen Laufs. Head-SHA und tatsächliche PR-Merge-Test-SHA werden
   getrennt erfasst. Alle zehn erwarteten Jobs müssen erfolgreich sein; fehlende,
   neutrale, übersprungene oder abgebrochene Jobs reichen nicht.
5. Lädt die neun erwarteten Artefakte je Lauf. Prüft GitHub-SHA-256, Quellen und
   Release-Manifeste sowie identische Windows-/Linux-Pakete. ZIP-Dateien werden
   nicht ins Projekt entpackt oder ausgeführt. JUnit-Zahlen und Skip-Identitäten
   bleiben pro Bericht erhalten, ohne überlappende Suiten als eindeutige Tests
   zu summieren. Alle erwarteten nativen Link-/Scannertests müssen vorhanden und
   erfolgreich sein. Einzige Ausnahme: der exakt benannte Windows-Junction-Test
   darf im Ubuntu-Artefakt ausschließlich mit `pytest.skip` und der Begründung
   `Windows native junction only` übersprungen sein. Windows und Scanner erlauben
   weiterhin keine Skips; siehe den verknüpften Korrekturbericht.
   Vier Browserberichte (CSP und drei integrierte Suiten) müssen erfolgreich und
   quellenfest sein. Bilder bleiben in den originalen CI-Artefakten verfügbar.
6. Stellt tatsächliche Run-Links im PR bereit. Prüft unabhängige Freigabe des
   Heads, GitHubs Reviewentscheidung, Checks/Statuskontexte, unveränderte Basis
   und Schutzregeln vor Merge. Kein Admin-Bypass. Abweichende Merge-Queue-,
   Signatur-, Linear-History- oder Deployment-Regeln blockieren einen unzulässigen
   Ersatz-Merge; Veröffentlichung und CI bleiben als Evidenz erhalten.
7. Verwendet einen regulären Merge-Commit mit erwartetem Head-SHA und bewahrt die
   Historie. Prüft danach den gemergten Baum gegen den Kandidaten und wartet auf
   vollständige CI des **neuen Main-SHA**. Scheitert sie, bleibt der tatsächliche
   Merge dokumentiert, Release-Ready aber falsch. Kein automatischer Revert,
   Rollback, Deployment oder Datenzugriff.
8. Erst dann wird SUCCESS ausgegeben und die finale Quellen-/CI-Abnahme im PR
   dokumentiert. Lokale Branches werden nicht umgeschaltet oder zurückgesetzt.
   Derselbe Aufruf verwendet vorhandene PRs/Läufe erneut. Ein bereits ausgeführter
   Merge benötigt zusätzlich den gehashten lokalen Merge-Beleg des vorherigen
   Laufs. Fremde unbestätigte Merges gelten nicht als eigene verifizierte Integration.

Der Launcher bewahrt Fehlercodes, Job-URLs und heruntergeladene Artefakte. Er
druckt keine Token, API-Fehlertexte, Joblogs, Formularwerte oder Secrets. Externe
Artefaktweiterleitungen erhalten keinen Authorization-Header. Fehler ergeben
Exit 2, Erfolg Exit 0; PowerShell gibt diesen Code unverändert weiter und hat
keinen separat ausgeführten, irreführenden SUCCESS-Befehl.

## Neue Evidenz und Dokumentation

Jeder Aufruf erzeugt `.verification/github-release-<UUID>/` mit:

- `acceptance.json` und `RELEASE_ACCEPTANCE.md`: genaue Quellen, PR, Merge, Runs
  und getrennte Status für Kandidaten-CI, finale Main-CI, Review und Deployment.
- Schutz-/Review-/Merge-Gate-Belegen ohne Reviewtexte oder Zugangsdaten.
- Jobresultaten, originalen ZIP-Artefakten, Hashes und validierten Quell-, JUnit-,
  Browser- und Release-Daten pro Run/Attempt.
- `evidence-sha256.json`: Integritätsmanifest der gesamten lokalen Übergabe.

Das sind tatsächliche Ergebnisberichte, keine vorausgefüllten Erfolgsvorlagen.
Nachträgliche CI-Daten werden nicht automatisch als neuer Commit in den gerade
getesteten Stand geschrieben; so entsteht keine Dokumentationscommit-/CI-Schleife.
PR-Kommentare und lokale Berichte bewahren die endgültigen Referenzen. Frühere
Originale bleiben unangetastet. Ein automatischer Bilderdownload ist **keine
neue Sichtprüfung**; CI-Bilder und Skip-Belege sind Teil des unabhängigen Reviews.

## Prüfung des Launchers und Status

Gezielte Offline-Tests prüfen CI-Gates, fehlende Jobs, falsche Quellen,
Browserteilberichte, native Skips, ZIP-Pfade, Token-Schutz bei Weiterleitung,
unlesbare Regeln, veraltete/Selbst-/Bot-Reviews, lokale Änderungen und den
vollständigen simulierten Ablauf bis zur neuen Main-CI. Die Simulation ist keine
ausgeführte GitHub-Abnahme. PowerShell wird zusätzlich syntaktisch geprüft.
Keine Wiederholung der bestandenen Frontend-, Excel-, Toolbar-, MFA- oder
PostgreSQL-Suiten. Ergebnisse stehen im Abschlussbericht dieser Übergabe.

Tatsächlich ausgeführt: **34 Offline-Regressionen bestanden (0,27 s)**;
JUnit: `.verification/github-release-launcher-tests-final.xml`.
PowerShell-Parser und `git diff --check` erfolgreich. Frühere Testzwischenstände
bleiben erhalten; Fehler in Test-ZIP-Erzeugung, TEMP-Fixtures und der anfänglichen
Artefaktnamenprüfung wurden vor diesem Ergebnis behoben. Dies betraf ausschließlich
die neue Release-Automatisierung. Ein zusätzlicher lesender API-Probeaufruf ergab
`github_network_unavailable`; Nachweis:
`.verification/github-release-network-probe.json`.

**Aktuell:** integriert und lokal abgenommen; Hosted CI, unabhängiges Review und
Main-Merge ausstehend; noch nicht RELEASE READY. Deployment weiterhin gesperrt,
keine Freigabe für reale kommunale Daten oder externe Hosts.
