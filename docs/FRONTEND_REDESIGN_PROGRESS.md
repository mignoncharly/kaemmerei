# Frontend-Redesign: Ausgangsstand und Fortschritt

Ausgangspunkt: U026 `3d4a180`, Branch `redesign/frontend-dashboard` in separatem
Worktree `OPEN_HERZ_Vertragsregister_Redesign`. Alle 30 lokalen geänderten/neuen
Dateien wurden zuerst kopiert. Original, STRATO und Release-Evidenz bleiben erhalten.
Die Kopien sind Vorarbeiten, keine Änderungen dieses Redesigns.

## Bestand vor Implementierung

FastAPI/Jinja, 16 HTML-Templates, eine gewachsene CSS-Datei, JavaScript ausschließlich
für Meldungen. Keine Node-Build-Pipeline erforderlich. Keine externe Schrift/CDN.
Alle Seiten erben base.html; bislang horizontale, umbrechende Kopf-Navigation.
Das Root-Listing enthält bereits fachbereichsgefilterte Kennzahlen und Fristen.
Vertragsaktionen und Dokumente liegen im Detail, keine globale Dokumentenroute.
Keine zusätzliche Benachrichtigungs-, Such- oder Freigabe-API vorhanden.

| Template | Aktionen und Zustände | Layout vorher / Ziel | Responsive und Testziel |
|---|---|---|---|
| list.html | echte Suche, acht Filter, Pagination, Export, Import, leere Treffer | überladene Übersicht / Bestand mit Filterbereich | Tabelle lokal scrollbar, alle Filter mit Labels; phase8, Browser |
| detail.html | Bearbeiten, Aufgaben, Prüfungen, Zuweisung, Upload, Ersetzen, DMS, Hold, Archivieren, Historie | lange unstrukturierte Seite / Abschnittsnavigation, Panels | keine Seitenüberläufe; Dokument- und Workflowtests |
| form.html | Neuanlage/Bearbeiten, Fehler mit Werterhalt, Versionskonflikt | ungegliederte Felder / benannte Gruppen | einspaltig mobil, Fokus und Pflichtfelder; phase8, Browser |
| users.html | Konten anzeigen, Anlegen, Verwalten | einfache Tabelle / Admin-Bestand | Tabellenregion, RBAC; phase5/8 |
| user_form.html | Rollen, Fachbereich, Freigabefähigkeit, Passwort, Sperren | Grundformular / Kontodaten und Rechte | Labels, Fehler, Sitzungsentzug; phase5/8 |
| identities.html | Fachbereiche, Kontakte, Teams, Mitgliedschaft, Audit | weitgehend roh / gegliederte Editorlisten | Labels, Checkboxen, Umbruch; phase4/8 |
| integrations.html | Tokens anlegen, rotieren, Rechte, widerrufen | teilweise roh / sichere Verwaltungsbereiche | lange Geheimnisse umbrechen; phase7/9 |
| review_inbox.html | persönliche Aufgaben und entscheidbare Prüfungen | rohe Listen / zwei Aufgabenbereiche | Status und leere Zustände; phase8 |
| reports.html | Kennzahlen, historische Beobachtungen, Fristenpagination | gemischte Tabellen / Berichte mit Hinweisen | Tabellenregionen, begrenzte Werte; report_projection/phase8 |
| login.html | Login, falsche Angaben, Rate-Limit, Abmeldehinweis | schlicht / eigenständiges Anmeldelayout | Passwortmanager, Tastatur; security/browser |
| password.html | Erstwechsel, Kontopasswort, Fehler | roh / Sicherheitsformular | Erstwechsel ohne Hauptnavigation; identity/browser |
| mfa.html | Enrollment, Schlüssel, Codeprüfung, Abbrechen, Fehler | roh / Anmeldeschritt | keine geheime Screenshot-Evidenz; phase9_mfa/browser |
| import_result.html | Importfehler, erfolgreicher Abschluss | Grundpanel / Ergebniszustand | lesbare Fehlerliste; phase7/browser |
| error.html | 400/401/403/404/409/413/422/429/503, sichere Wiederherstellungswerte | Einzelpanel / integrierte Fehleransicht | Geheimnisse ausgeschlossen; phase8 |
| workflow_conflict.html | Konflikt und unveränderte eingereichte Angaben | Einzelpanel / Abgleichansicht | kein automatisches Wiederholen; phase8 |
| base.html | Navigation, Logout-CSRF, Hinweise | horizontale Leiste / Sidebar und Topbar | Tastatur, Fokusfalle, Escape, 320–1440 px |

API, XLSX, Dokumentdownloads und Health bleiben unverändert maschinenlesbar;
es werden keine erfundenen UI-Ziele dafür eingeführt. Serverfehler erhalten eine
generische Fehlerseite ohne interne Ausnahmeinformationen.

## Designsystem

Navy-Sidebar 248 px, warmes Hellgrau als Arbeitsfläche, weiße Panels, Petrol als
Akzent. Systemschrift, 4-px-Abstandsraster, klare 1-px-Konturen, 8–12-px-Radien.
Gemeinsame Buttons, Formulare, Tabellen, Meldungen, Status-Chips, leere Zustände,
Aufgaben-/Dokumentlisten, Details-Disclosure und Pagination. SVG-Icons lokal im
Template, kein zusätzlicher Runtime- oder Netzwerkbedarf. Native Formular-POSTs,
progressive Navigation, keine parallele Frontend-Berechtigungslogik.

## Fortschritt

- Inventar und Ausgangsstand erfasst; Baseline-Tests und Browserlauf gestartet.
- Umsetzung und Verifikation folgen in FRONTEND_IMPLEMENTATION_REPORT.md.
