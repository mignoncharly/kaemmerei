# Abschließende Release-Verifikation und Übergabe

Stand: 23.10.2026. Dieser Bericht ersetzt die **Handlungsaufforderungen** der
früheren Debuggingnotizen. Deren Ergebnisse und Originaldateien bleiben erhalten.
Aktuelle freigegebene GitHub-Veröffentlichung und ein einziger Windows-Abschlusslauf:
[GITHUB_RELEASE_HANDOFF.md](GITHUB_RELEASE_HANDOFF.md). Diese Übergabe ergänzt den
lokalen Abnahmestand; sie behauptet noch keinen Hosted-Erfolg.
Kanonischer Arbeitsort: `C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase`, Branch
`release/redesign-integration`. Keine weitere Redesign- oder Debuggingphase.

## Eingefrorener Stand

Erfolgreich geprüfter Toolbar-Stand:
**461e030b015c37e47c6204a5b6c7cf6dc35cd61f**.
Toolbar, Anwendung, Assets und Browserprüfer werden ohne nachgewiesenen neuen
Defekt nicht geändert. Die jetzige Konsolidierung ändert ausschließlich Dokumentation.
Die SHA-/Git-Blob-Fingerprints der zentralen Dateien stehen im
[Abnahmemanifest](RELEASE_ACCEPTANCE_MANIFEST.json).

## Konsolidierte Ergebnisse mit genauer Revisionsbindung

| Prüfung | Tatsächlich getestete Revision | Ergebnis | Lokales Evidenzverzeichnis unter `.verification/` |
|---|---|---|---|
| Frontend einschließlich MFA und Rollen | `e1f262bbfe4ff4a039afa3a49aad995a5ac3efcf` | 373 Browserchecks bestanden | `integrated-browsers-fd66fa456b6d4aa79080a14ffa5c53c0/redesign/` |
| Excel-Auswahl, Einzel-/Bulk-/Gesamtexport, Import | `e163dd50efc61f87bd7ed6d1e4fa4a69f8626625` | 383 Browserchecks bestanden, Exit 0 | `excel-browser-43cef1bdbffc4cddb248b6a5f535fb92/` |
| Toolbar, Filter, Fokus und Reflow | `461e030b015c37e47c6204a5b6c7cf6dc35cd61f` | **356 Browserchecks bestanden, Exit 0** | `toolbar-browser-706282027fd4465db3793aaba3afea79/` |
| Vollständige PostgreSQL-Suite | `d5f402d9f93d25231fb40aa843395da70f5267eb` | 521 bestanden, 2 Skips, 15 erfolgreiche Untertests; Exit 0 | `browser-fix-postgresql-d5f402d/` |
| Relevante abschließende Regressionen | `461e030b015c37e47c6204a5b6c7cf6dc35cd61f` | 146 bestanden, keine Skips | `filter-dismissal-461e030-98fec7b125a94e45a69aae2fd3f24fb5/` |

Der Frontend-Kindlauf war erfolgreich, obwohl sein damaliger integrierter Parent
wegen des späteren Toolbarfehlers insgesamt scheiterte. **Dieser Parent wird nicht
nachträglich als erfolgreich bezeichnet.** Ebenso werden die drei verschiedenen
Browserrevisionen nicht als ein gemeinsamer ausgeführter Lauf ausgegeben.
U026s zehn frühere CI-Jobs gehören ausschließlich zu
`3d4a180297db801293e4b86e42e9f60a55fbca86` und belegen keinen neuen Kandidaten.

Die JSON-Kindberichte wurden gegen die SHA-256 im jeweiligen Parentbericht
abgeglichen; Quelle, Erfolg, Exitcode, eindeutige Prüfnamen, Checkzahl und
`source_unchanged` stimmen. Alle referenzierten Bilder existieren.
**206 Original-Ergebnis-/Bildartefakte** sind im Manifest gehasht; zusätzlich
ist der JUnit-Nachweis der 146 Regressionen verzeichnet. Die PostgreSQL-JUnit-Datei
stimmt mit dem Runner-Hash überein. Ihre 538 Einträge umfassen 523 Tests und
15 Untertests; daraus werden keine zusätzlichen Haupttests erfunden.

PostgreSQL-Skips: tatsächliche symbolische Speicherverknüpfung unter den lokalen
Windows-Rechten und realer ClamAV mit offiziellen aktuellen Definitionen. Beide
bleiben offen und haben eigene zwingende Hosted-CI-Prüfungen. Keine xfails oder
entfernten Sicherheitsprüfungen.

## Welche Wiederholung ist erforderlich?

| Bereich | Tatsächliche Änderungen seit seinem erfolgreichen Lauf | Entscheidung |
|---|---|---|
| Frontend/MFA | Keine Änderungen an Anwendung, Templates, CSS, Migrationen, Deployment oder Runtime-Abhängigkeiten seit e1f262b. Später nur Toolbar-Runner, Diagnose und Tests. | Kein erneuter lokaler Frontend-Lauf. |
| Excel | Seit e163dd5 nur Toolbar-Fokusutility, Toolbar-Runner und deren Tests. Excel-Runner, verwendete Layoututility und Anwendung unverändert. | Kein erneuter lokaler Excel-Lauf. |
| PostgreSQL | Seit d5f402d nur `app/static/interface.js` im Runtime-Bereich geändert: modaler Tab-Umlauf/ARIA, mittlerweile browsergeprüft. Backend, Modelle, Migrationen, Runtime-Lock, Betriebsdateien unverändert. Neue Diagnose-/Fokustests wurden separat bestanden. | Kein erneuter vollständiger lokaler PostgreSQL-Lauf. |
| Toolbar | Erfolgreicher Lauf liegt auf dem eingefrorenen Code; danach nur Dokumentation. | Kein erneuter lokaler Toolbar-Lauf. |
| Final-source CI | Für den integrierten Review-Kandidaten noch kein Hosted-Lauf vorhanden. Auch saubere Lock-Installation, echte Scanner-/Link-Gates und plattformübergreifende Artefakte benötigen die bestehende CI. | Ein vollständiger regulärer Workflow auf dem exakten Review-Commit bleibt erforderlich. |

Die Git-Differenzen stehen maschinenlesbar im Manifest. Diese Begründung belegt
unveränderte relevante Bereiche; sie ist **kein behaupteter Testlauf auf einer
anderen Revision**. Neue relevante Codeänderungen erfordern gezielt passende Tests.
Reine weitere Dokumentationsänderungen lösen keine neue manuelle Browserrunde aus.

## Tatsächliche Sichtprüfung

Am 23.10.2026 wurden 18 vorhandene Browserbilder geprüft: Escape-Rückgabe und
stabil geöffnete Filter bei 390/768/1280/1440 px, Excel-Import bei denselben Breiten,
aktive Kultur-Filter, Prüferansicht sowie Auswahl-/Exportleiste mobil und Desktop.
Die Dateiliste steht im Manifest. Für lesbare Prüfung wurden lokale Ausschnitte
der Originalbilder erzeugt; keine neuen Browseraufnahmen oder Mockups.

Ergebnis: sichtbare Fokusrahmen, korrekt angeordnete Trigger und Dialogfelder,
keine unbeabsichtigte Seitenverbreiterung in den geprüften Ansichten. Breite
Vertragstabellen scrollen lokal; Spalten außerhalb dieses Bereichs sind erwartbar
abgeschnitten. Mobile Importaktionen sind gestapelt, die drei Desktopaktionen
haben gleiche Höhe und Zentrierung. Die ersten Tabellenzeilen liegen früh im
Viewport. Kultur und Prüfer zeigen keine administrativen Navigationsgruppen;
Prüfer hat keine Erfassungsaktion.

Die zwei frühen `open-admin`-Bilder zeigen noch die bestehende 120ms-Einblendung.
Die späteren `expanded-admin`-Bilder sind deckend und korrekt. Daraus ergibt sich
kein neuer Implementierungsauftrag. Keyboard-/Inert-/Escape-Nachweis stammt aus
den bestandenen Browserchecks; dies ist kein vollständiges Screenreader-Audit.
Originalberichte mit `visual_inspection: NOT_PERFORMED` werden nicht umgeschrieben;
die jetzt tatsächlich erfolgte repräsentative Sichtprüfung ist separat dokumentiert.

## Abschließendes Verfahren: ein Review-/CI-Durchlauf

1. **Lokal abgeschlossen:** Quell-/Evidenzabgleich und Sichtprüfung wie oben.
   Dokumentation versionieren; danach das vorhandene Release-Buildverfahren
   zweimal auf demselben Commit ausführen, Bytes/Manifest vergleichen und das
   gepackte Runtime-Smoke mit isolierter In-Memory-SQLite prüfen. Hash und genaue
   Commit-SHA im lokalen `release-summary.json` und `runtime-smoke.json` erhalten.
   Diese Artefaktprüfung ersetzt keine PostgreSQL- oder saubere CI-Installation.
2. **Repository-Gate:** Über den autorisierten GitHub-Zugang den tatsächlichen
   Default-/Zielbranch, Branchschutz und Rulesets lesen; Remote-Vorsprung gegenüber
   der lokalen Basis prüfen. Keine erzwungenen Pushes, kein Überschreiben neuerer
   Arbeit. Veröffentlichung und regelkonformer Merge nach CI und Review sind
   inzwischen ausdrücklich autorisiert. Der [PR-Text](INTEGRATED_RELEASE_PR.md)
   ist vorbereitet; die aktuelle GitHub-Übergabe beschreibt den Abschlusslauf.
3. **Final-source CI:** Kandidat über den bestehenden Review-Workflow bereitstellen,
   sobald Zugang und Freigaben dies erlauben. Unveränderte Workflow-Datei
   `.github/workflows/phase1-verification.yml`: **zehn Jobausführungen** aus acht
   Jobdefinitionen. Diese prüfen sauberes Locked Release auf Windows/Linux,
   Artefakt-Reproduzierbarkeit, native Speicherlinks auf beiden Betriebssystemen,
   Browser/CSP/MFA samt allen drei Redesign-Suiten, realen Scanner, native
   PostgreSQL-Werkzeuge, SQLite und PostgreSQL einschließlich Betriebsprüfungen.
4. **Fail closed:** Nur ein vollständig erfolgreicher Lauf auf dem dokumentierten
   Commit erfüllt dieses Gate. Run-URL, Event, Head-SHA und gegebenenfalls gesonderte
   PR-Merge-Test-SHA festhalten. Keine übersprungenen/abgebrochenen Pflichtjobs als
   bestanden werten. Bei einem Fehler zuerst die vollständige gemeinsame Evidenz
   auswerten, dann ausschließlich den nachgewiesenen Defekt bearbeiten.
5. **Abschlussnachweis:** Alle Jobresultate, JUnit-Zahlen/Skips und heruntergeladenen
   Artefakthashes erfassen; Windows-/Linux-Releasebytes und Source-Metadaten prüfen.
   CI-Browserbilder repräsentativ sichten. Merge erst gemäß den tatsächlich
   geltenden Reviews/Schutzregeln. Entsteht beim Merge ein neuer Quellstand, dessen
   Pflicht-CI ebenfalls abwarten. Kein unbestätigter Kandidat wird zur Auslösung
   eines Deployments gemerged.
6. **Getrennte Betriebsfreigabe:** Externes Deployment bleibt gesperrt, solange
   kein genehmigter Windows/PostgreSQL/TLS-Zielserver mit Scanner, Backup/Restore,
   Zugriffsschutz und Betriebsabnahme existiert. Das hindert Code-Review und CI
   nicht. Echte kommunale Daten bleiben nicht autorisiert.

**Jetzt ist kein weiterer lokaler interaktiver Verifikationslauf erforderlich.**
Sollte sich später eine konkret notwendige Hosted-Browserprüfung als technisch
unmöglich erweisen, wird höchstens einmal der bereits vorhandene integrierte
Fail-fast-Launcher für alle drei Suiten verwendet, auf exakt festgelegter SHA.
Es werden keine weiteren einzelnen PowerShell-Debuggingaufträge ausgegeben.

## Externe Blocker und Status

Erneuter lesender Versuch `git ls-remote --symref origin HEAD`: Exit **128**;
GitHub:443 über den konfigurierten lokalen Netzwerkpfad nicht erreichbar.
Kein Proxy-/Credential-/ACL-Umbau. Kein GitHub-Connector und keine gestartete neue
Workflow-Ausführung. Deshalb keine aktuelle Branchschutzbestätigung, Run-URL oder
erfundene Hosted-Ergebnisse. Veröffentlichung/Review/CI bleiben der einzige
noch offene Code-Release-Schritt; nicht eine weitere lokale Browserkorrektur.

- **INTEGRATED:** ja, kanonische Anwendung mit vollständigem Redesignverlauf.
- **TESTED:** obige revisionstreuen lokalen Ergebnisse und dokumentierter Scope-Abgleich.
- **REVIEW PREPARED:** ja, Kandidat, eingefrorene Implementierung, Manifest und PR-Text lokal vorhanden.
- **RELEASE READY:** noch nein; finale CI und geltendes Repository-Review ausstehend.
- **DEPLOYED:** nein.
- **DEPLOYMENT BLOCKED:** kein freigegebener Zielserver; getrennt vom Code-Release.

Lokale Konsolidierungsevidenz:
`.verification/release-consolidation-d25950ed035d478fb1366e2f4e647701/`.
Sie enthält Integritätsauswertung, Sichtprüfungs-Ausschnitte und abschließende
Build-/Smoke-Ergebnisse. Originale bleiben in ihren bisherigen Verzeichnissen.
Kein Reset/Clean, kein weiterer Worktree, keine Änderung an STRATO oder Produktionsdaten.
