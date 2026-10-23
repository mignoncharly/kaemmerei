# Integriertes OPEN.HERZ-Dashboard mit abgesicherter Vertrags- und Excel-Bedienung

Das bisher getrennte Frontend ist in der kanonischen Anwendung zusammengeführt.
Alle vorhandenen Rollenoberflächen nutzen die gemeinsame Navigation und das
Designsystem. Die Vertragsübersicht zeigt die Daten direkt; Suche/Filter sind
als zugänglicher modaler Popover beziehungsweise mobiler Drawer erreichbar.
Explizit ausgewählte Verträge können einzeln oder gemeinsam als Excel exportiert
werden, mit serverseitiger Einzelautorisierung und unveränderten Exportgrenzen.
Der create-only Excel-Import hat gleichmäßig ausgerichtete Bedienfelder und klare
Datei-/Validierungsrückmeldung. Backend-Sicherheitsregeln und Migrationen bleiben
erhalten; Testdaten und private Verifikationsevidenz sind kein Deploymentinhalt.

Lokale Abnahme (jeweils tatsächlich getestete Revision):

| Suite | Ergebnis | Revision |
|---|---|---|
| Frontend/MFA/Rollen | 373 Browserchecks bestanden | e1f262b |
| Excel | 383 Browserchecks bestanden | e163dd5 |
| Toolbar/Responsive/Keyboard | 356 Browserchecks bestanden | 461e030 |
| PostgreSQL gesamt | 521 bestanden, 2 Skips, 15 Untertests | d5f402d |
| Abschließende gezielte Regressionen | 146 bestanden, keine Skips | 461e030 |

Die Anwendung ist seit dem Frontend-Erfolg unverändert; spätere Änderungen
betrafen Toolbar-Verifikation/Diagnose. Der unveränderte Backend-/Migrationsscope
und die Änderungen zwischen allen Prüfrevisionen sind in
[FINAL_RELEASE_ACCEPTANCE.md](FINAL_RELEASE_ACCEPTANCE.md) und
[RELEASE_ACCEPTANCE_MANIFEST.json](RELEASE_ACCEPTANCE_MANIFEST.json) dokumentiert.
Vorhandene Screenshots bei 390/768/1280/1440 px wurden repräsentativ geprüft.
Die Ergebnisse werden nicht als ein gemeinsamer ausgeführter Lauf ausgegeben.

Vor Merge erforderlich: vollständige bestehende GitHub-CI auf dem exakten
Review-Kandidaten und geltende Reviews/Branchschutzregeln. Die beiden lokalen
PostgreSQL-Skips benötigen die vorhandenen nativen Link-/ClamAV-CI-Gates.
U026s ältere CI ersetzt diese Prüfung nicht. Die finale Run-URL und Artefakthashes
werden nach tatsächlicher Ausführung ergänzt; derzeit keine Hosted-Abnahme.

Kein Deployment Bestandteil dieses Reviews. Ein externes Pilotziel und die
Verarbeitung echter kommunaler Vertragsdaten sind weiterhin nicht freigegeben.
