# Korrektur des plattformspezifischen Release-Gates

## Bestätigte Ursache und begrenzte Änderung

PR: https://github.com/mignoncharly/kaemmerei/pull/1.
Geprüfter ursprünglicher Kandidat: `7ba43ff38cac14c896be612637248cb914e3649a`.
Der Launcher verlangte in jedem nativen Link- und Scanner-JUnit-Bericht null
Skips. Die vorhandene Plattformmarkierung des Windows-Junction-Tests führte
deshalb auf Ubuntu zum falschen Blocker `mandatory_native_or_scanner_tests_skipped`,
obwohl alle dort anwendbaren Prüfungen erfolgreich waren.

Die korrigierte Regel prüft zusätzlich die vollständige, exakte Testinventur:

| Artefakt | Erforderliche Tests und zulässiger Zustand |
|---|---|
| `native-storage-links-windows-latest` | `tests.test_phase5::test_actual_linked_storage_is_rejected` und `tests.test_storage_links::test_actual_windows_junction_storage_and_parent_are_rejected`, beide bestanden |
| `native-storage-links-ubuntu-24.04` | Derselbe Symlink-Test muss bestanden sein. Derselbe Junction-Test muss vorhanden sein; nur für ihn ist `type=pytest.skip`, `message=Windows native junction only` zulässig. |
| `document-scanner-verification` | `tests.test_phase5::test_real_clamav_engine_with_current_official_database`, bestanden |

Die nativen Artefakte müssen genau `native-storage-links.xml`, das Scannerartefakt
genau `phase5-scanner.xml` enthalten. Fehlende, doppelte, umbenannte oder unerwartete
Tests/Berichte, Fehler, übersprungene anwendbare Tests, xfail-Klassifizierungen und
andere Skip-Gründe blockieren weiterhin. Keine allgemeine Skip-Freigabe. Die
zulässige Ausnahme wird als `not_applicable_windows_junction_on_ubuntu` ausgewiesen.
Keine Änderung an Anwendung, Sicherheitsregeln, Datenbank, Browsern oder CI-Workflow.

## Tatsächlich erhaltene Hosted-Evidenz

Das lokale Originalverzeichnis ist
`.verification/github-release-8917a40cd64e472f8cb5047ee3b20fd1/`.
Seine neun ZIPs, Jobmetadaten und der ursprüngliche Abbruchbericht gehören zum
**Push-Lauf [39936271918](https://github.com/mignoncharly/kaemmerei/actions/runs/39936271918),
Attempt 1**, auf exakt `7ba43ff`. Zehn Jobs sind dort als erfolgreich abgeschlossen
dokumentiert. Der Nutzer nennt zusätzlich Lauf **39936278677**; dafür liegt in
diesem Verzeichnis keine heruntergeladene Evidenz vor. Dieser zweite Lauf wird
nicht mit dem Push-Lauf gleichgesetzt oder als unabhängig geprüft ausgegeben.
GitHub ist aus der Agentenumgebung weiterhin nicht erreichbar.

Originale Archive (SHA-256, gegen gespeicherte GitHub-Download-Digests geprüft):

| Artefakt | SHA-256 |
|---|---|
| `runtime-release-ubuntu-24.04` | `2591d0e6eac8afb22886cea018a6b08dbc8436fa007bad5259275494e1d32847` |
| `runtime-release-windows-latest` | `1c0da679286b29ebbabf95fd171dbfd3c64e3fd75624f7c302ce1596b0bb8f6e` |
| `native-storage-links-ubuntu-24.04` | `6c2debaf1da1fc6514efc86b92b80c486fc0cf9dc5eff3293ee1c34c45d0bfb6` |
| `native-storage-links-windows-latest` | `29c8a046f78db6f297e36b571a8dd52c75f6077727f8176187590d1e6b87bb75` |
| `document-scanner-verification` | `1699767e5e893588380930cc1d0d993cfb73377fc8e017bf646660155a9d12cc` |
| `phase8-browser-verification` | `669032272e097c1ecd0ec7f553810b2c5f50623252225c3b81c1aaf93d800143` |
| `native-postgresql-verification` | `9bd4f3850b9c363b4c315a2e7796406d2d965c85317be01bb6bbf5d0bb35aeba` |
| `postgresql-verification` | `870ebd5404d0b1e3c009e9d7fec49399adbce879a6b65ceecf8a92073e2b546f` |
| `sqlite-verification` | `b68cf753779366e6d6bb3e780c4e90e3c11125d2d023d52d42336000553c6547` |

Tatsächlich inspizierte JUnit-Inhalte:

- Windows: 2 bestanden, 0 Skips. XML-SHA-256
  `83f9387395ffb047b55c81f2826f6d6aea4fe580a64b5c861dc2048c53d2eba1`.
- Ubuntu: 1 bestanden, exakt 1 oben klassifizierter Junction-Skip. XML-SHA-256
  `890cff04f4b4a524070d0c35ab2bf611d129ebae5d22f8c20f26e8262ffc7b0c`.
- Reales ClamAV: 1 bestanden, 0 Skips. XML-SHA-256
  `8ed48e2b54fcadf98563ee34abe4ee6429c18925f9bf5e332e90b94fd730a84e`.

Alle neun ZIPs wurden mit der korrigierten Policy erneut erfolgreich validiert,
einschließlich Quellrevision, Browserresultaten, JUnit und Release-Manifeste.
Windows-/Linux-Releasepakete sind identisch, SHA-256:
`05aae155df0316362f32b1fabd0e2f53aa0adc863a9c2171624b90377ace669f`.
Das vollständige ursprüngliche Evidenzmanifest stimmt weiterhin. Kein Original
wurde geändert und kein historischer Abbruchbericht nachträglich überschrieben.

Neue Auswertung:
`.verification/github-platform-policy-0f2b651d11f041c49929136df7516475/revalidation.json`.
Das ist eine erneute **Artefaktprüfung des alten Kandidaten**, kein neuer
Anwendungs-/Browserlauf und keine behauptete CI-Ausführung auf dem Korrekturcommit.

## Regressionen und Abschluss

**82 gezielte Tests bestanden, 0 Fehler/Skips, 0,38 s.** JUnit:
`.verification/github-platform-skip-tests-publication.xml`.
Positive und negative Fälle decken Plattform, Testidentität, Skip-Typ/-Grund,
fehlende/duplizierte/fehlgeschlagene Tests, Berichtsinventur und die bestehende
Review-/CI-Absicherung ab. Keine erneuten Anwendungs-, PostgreSQL- oder Browsertests.

Der Launcher erhält zusätzlich `-PullRequest 1`, damit der neue Commit den
bestehenden Branch `review/integrated-release-7ba43ff38cac` aktualisiert und keinen
zweiten PR erzeugt. Er verlangt dieselbe Repository-/Branchzuordnung und eine
Fast-Forward-Abstammung vom tatsächlichen Remote-Head, verwendet keinen Force-Push
und prüft den veröffentlichten Head erneut. Unabhängige Reviews müssen weiterhin
den **neuen** Head freigeben; alte Freigaben zählen nicht.
Ein PR-Kommentar kennzeichnet die neue SHA ausdrücklich als Nachfolger des alten
Kandidaten im ursprünglichen PR-Text, ohne bereits CI-Erfolg zu behaupten.

Der einzelne Windows-Aufruf mit der neuen SHA wird in der Übergabeantwort
angegeben. Er aktualisiert PR #1, sammelt die zwingende neue Final-Source-CI,
wartet auf unabhängige Freigabe und Repository-Gates und prüft nach einem zulässigen
Merge auch dessen neue Main-SHA. GitHub-Veröffentlichung und neue CI bleiben bis
zur tatsächlichen Ausführung ausstehend. Kein vorzeitiges RELEASE READY, kein
Deployment und keine Änderung an STRATO oder Produktionskonfiguration.
