# Frontend-Routenmatrix

Statisch aus allen Route-Dekoratoren in `app/*.py` erzeugt. GET-Seiten, POST-Aktionen,
Downloads und maschinenlesbare Endpunkte sind vollständig aufgeführt. Testverweise
sind Quelltextzuordnungen, keine Behauptung ausgeführter Tests.

| Methode / URL | Implementierung / Zweck | Rendering | Zugriff | Bestehende Testzuordnung |
|---|---|---|---|---|
| POST `/contracts/{contract_id}/documents/{document_id}/replace` | `document_routes.py:28` / replace_document | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/documents/{document_id}/link` | `document_routes.py:49` / correct_link | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/documents/{document_id}/hold` | `document_routes.py:71` / hold | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| GET `/account/password` | `identity_routes.py:27` / password_page | password.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_phase2.py, test_phase3.py, test_phase9_mfa.py |
| POST `/account/password` | `identity_routes.py:32` / change_password | password.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_phase2.py, test_phase3.py, test_phase9_mfa.py |
| GET `/admin/identities` | `identity_routes.py:69` / identities | identities.html | Administration; serverseitige Prüfung | test_phase2.py, test_phase3.py |
| POST `/admin/identities/{entity}/{identity_id}` | `identity_routes.py:81` / maintain_identity | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase2.py, test_phase3.py |
| POST `/admin/recipient-memberships` | `identity_routes.py:135` / membership | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase2.py |
| POST `/contracts/{contract_id}/reviews/{review_id}/assignment` | `identity_routes.py:160` / assign_review | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| GET `/reviews` | `identity_routes.py:202` / review_inbox | review_inbox.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_phase1.py, test_phase2.py, test_phase3.py, test_phase4.py, test_phase5.py |
| GET `/api/v2/snapshot` | `integration.py:132` / snapshot | JSON / Datei | Integrationstoken / Scope | test_phase6.py, test_phase9.py, test_phase9_mfa.py |
| GET `/api/v2/changes` | `integration.py:157` / changes | JSON / Datei | Integrationstoken / Scope | test_phase6.py |
| GET `/api/v2/contracts/{contract_id}` | `integration.py:181` / detail | JSON / Datei | Integrationstoken / Scope | test_phase6.py, test_phase7.py |
| GET `/api/v2/contracts/{contract_id}/history` | `integration.py:186` / history | JSON / Datei | Integrationstoken / Scope | test_phase6.py, test_phase7.py |
| GET `/api/v2/contracts/{contract_id}/documents/{document_id}` | `integration.py:209` / document | JSON / Datei | Integrationstoken / Scope | test_phase6.py, test_phase7.py |
| GET `/health/live` | `main.py:585` / live | JSON / Datei | Öffentlich; bestehende Schutzmaßnahmen | test_phase9.py |
| GET `/health/ready` | `main.py:589` / ready | JSON / Datei | Öffentlich; bestehende Schutzmaßnahmen | test_phase9.py |
| GET `/login` | `main.py:625` / login_page | login.html | Öffentlich; bestehende Schutzmaßnahmen | test_app.py, test_phase9.py, test_phase9_mfa.py |
| POST `/login` | `main.py:637` / login | login.html | Öffentlich; bestehende Schutzmaßnahmen | test_app.py, test_phase9.py, test_phase9_mfa.py |
| POST `/logout` | `main.py:668` / logout | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_phase1.py, test_phase2.py, test_phase3.py, test_phase4.py |
| GET `/admin/users` | `main.py:679` / users_page | users.html | Administration; serverseitige Prüfung | test_phase2.py, test_phase8.py |
| GET `/admin/integrations` | `main.py:699` / integrations_page | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase6.py |
| POST `/admin/integrations` | `main.py:705` / create_integration | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase6.py |
| POST `/admin/integrations/{token_id}/revoke` | `main.py:747` / revoke_integration | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase6.py |
| GET `/api/v1/departments` | `main.py:768` / api_departments | JSON / Datei | Integrationstoken / Scope | test_acceptance.py |
| GET `/api/v1/contracts` | `main.py:777` / api_contracts | JSON / Datei | Integrationstoken / Scope | test_acceptance.py, test_phase1.py, test_phase2.py, test_phase3.py, test_phase6.py, test_phase8.py |
| GET `/api/v1/contracts/{contract_id}/documents/{document_id}` | `main.py:847` / api_document | JSON / Datei | Integrationstoken / Scope | test_acceptance.py, test_phase3.py |
| GET `/admin/users/new` | `main.py:858` / new_user_page | user_form.html | Administration; serverseitige Prüfung | test_phase2.py, test_phase8.py |
| POST `/admin/users/new` | `main.py:879` / create_user | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase2.py, test_phase8.py |
| GET `/admin/users/{user_id}/edit` | `main.py:900` / edit_user_page | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase2.py, test_phase8.py |
| POST `/admin/users/{user_id}/edit` | `main.py:912` / update_user | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase2.py, test_phase8.py |
| GET `/contracts/import-template.xlsx` | `main.py:935` / download_import_template | JSON / Datei | Persönliche Sitzung; Objekt-/Fachbereichsrechte | Indirekte Workflow-Tests; Browsermatrix ergänzen |
| GET `/contracts/export.xlsx` | `main.py:944` / export_contracts | JSON / Datei | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_phase8.py |
| GET `/reports` | `main.py:997` / reports | reports.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_operational_monitoring.py, test_phase7.py, test_phase8.py, test_report_projection.py |
| POST `/contracts/import` | `main.py:1136` / import_contracts | import_result.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_phase7.py |
| GET `/` | `main.py:1274` / contracts | list.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | Indirekte Workflow-Tests; Browsermatrix ergänzen |
| GET `/contracts/new` | `main.py:1344` / new_contract | form.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_app.py, test_phase2.py, test_phase4.py, test_phase7.py, test_phase8.py, test_phase9_mfa.py |
| POST `/contracts/new` | `main.py:1352` / save_new | form.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_app.py, test_phase2.py, test_phase4.py, test_phase7.py, test_phase8.py, test_phase9_mfa.py |
| GET `/contracts/{contract_id}` | `main.py:1425` / detail | detail.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/tasks` | `main.py:1461` / create_contract_task | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/tasks/{task_id}` | `main.py:1486` / update_contract_task | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/reviews` | `main.py:1517` / create_contract_review | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/reviews/{review_id}` | `main.py:1553` / update_contract_review | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/documents` | `main.py:1595` / upload_document | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/documents/link` | `main.py:1643` / link_external_document | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| GET `/contracts/{contract_id}/documents/{document_id}` | `main.py:1673` / get_document | JSON / Datei | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| GET `/contracts/{contract_id}/edit` | `main.py:1686` / edit | form.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/edit` | `main.py:1699` / save_edit | form.html | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| POST `/contracts/{contract_id}/archive` | `main.py:1743` / archive | Weiterleitung / gemeinsamer Fehlerzustand | Persönliche Sitzung; Objekt-/Fachbereichsrechte | test_acceptance.py, test_app.py, test_browser_diagnostics.py, test_phase1.py, test_phase2.py, test_phase3.py |
| GET `/account/mfa` | `mfa_routes.py:42` / mfa_page | mfa.html | Ausstehende MFA-Sitzung | test_phase9_mfa.py |
| POST `/account/mfa/start` | `mfa_routes.py:50` / mfa_start | Weiterleitung / gemeinsamer Fehlerzustand | Ausstehende MFA-Sitzung | test_phase9_mfa.py |
| POST `/account/mfa` | `mfa_routes.py:62` / mfa_verify | mfa.html | Ausstehende MFA-Sitzung | test_phase9_mfa.py |
| POST `/admin/integrations/{token_id}/rotate` | `token_service.py:38` / rotate | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase6.py |
| POST `/admin/integrations/{token_id}/scope` | `token_service.py:58` / rescope | Weiterleitung / gemeinsamer Fehlerzustand | Administration; serverseitige Prüfung | test_phase6.py |
