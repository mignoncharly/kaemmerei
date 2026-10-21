import re
from sqlalchemy import select
from app.models import Contract, Revision, LoginSession
from tests.support import csrf_from, login, contract_payload, create_contract


def test_guest_has_no_access_and_login_required(environment):
    client, app = environment
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    response = client.post("/contracts/new", data=contract_payload(), follow_redirects=False)
    assert response.status_code == 303
    assert login(client, "admin").status_code == 303
    assert "Vertragsübersicht" in client.get("/").text


def test_csrf_enforced_on_login_create_edit_and_archive(environment):
    client, app = environment
    guest = client.get("/login")
    assert client.post("/login", data={"username": "admin", "password": "anything", "csrf_token": "invalid"}).status_code == 403
    assert login(client, "admin").status_code == 303
    assert client.post("/contracts/new", data=contract_payload()).status_code == 403
    record_id = create_contract(client)
    assert client.post(f"/contracts/{record_id}/edit", data={"version": 1}).status_code == 403
    assert client.post(f"/contracts/{record_id}/archive", data={"version": 1}).status_code == 403


def test_department_isolation_and_server_side_ownership(environment):
    client, app = environment
    login(client, "admin")
    id_a = create_contract(client, "1", "Vertrag A")
    id_b = create_contract(client, "2", "Vertrag B")
    client.post("/logout", data={"csrf_token": csrf_from(client.get("/").text)})
    login(client, "kultur")
    page = client.get("/")
    assert "Vertrag A" in page.text
    assert "Vertrag B" not in page.text
    assert client.get(f"/contracts/{id_b}").status_code == 404
    assert client.get(f"/contracts/{id_b}/edit").status_code == 404
    # A department user cannot supply a different department in the POST body.
    own_id = create_contract(client, "2", "Behauptet Bauamt")
    with app.state.session_factory() as db:
        assert db.get(Contract, own_id).department_id == 1
    # Reviewer has full read access, but no write access.
    client.post("/logout", data={"csrf_token": csrf_from(client.get("/").text)})
    login(client, "pruefer")
    assert "Vertrag B" in client.get("/").text
    assert client.get(f"/contracts/{id_a}").status_code == 200
    assert client.get("/contracts/new").status_code == 403
    assert client.get(f"/contracts/{id_a}/edit").status_code == 403


def test_create_edit_archive_history_and_conflict(environment):
    client, app = environment
    login(client, "admin")
    contract_id = create_contract(client)
    detail = client.get(f"/contracts/{contract_id}")
    assert "Mietvertrag Sporthalle" in detail.text
    form = client.get(f"/contracts/{contract_id}/edit")
    assert form.status_code == 200
    values = contract_payload(designation="Mietvertrag Sporthalle (neu)")
    values.update(csrf_token=csrf_from(form.text), version="1")
    success = client.post(f"/contracts/{contract_id}/edit", data=values, follow_redirects=False)
    assert success.status_code == 303
    assert client.post(f"/contracts/{contract_id}/edit", data=values).status_code == 409
    detail = client.get(f"/contracts/{contract_id}")
    assert "(neu)" in detail.text
    assert "Änderungshistorie" in detail.text
    csrf = csrf_from(detail.text)
    assert client.post(f"/contracts/{contract_id}/archive", data={"csrf_token": csrf, "version": 1}).status_code == 409
    archived = client.post(f"/contracts/{contract_id}/archive", data={"csrf_token": csrf, "version": 2}, follow_redirects=False)
    assert archived.status_code == 303
    assert client.get(f"/contracts/{contract_id}/edit").status_code == 409
    assert "Mietvertrag Sporthalle (neu)" not in client.get("/").text
    assert "Mietvertrag Sporthalle (neu)" in client.get("/?status=archived").text
    with app.state.session_factory() as db:
        revisions = db.scalars(select(Revision).where(Revision.contract_id == contract_id)).all()
        assert [x.action for x in revisions] == ["created", "updated", "archived"]
        assert revisions[1].before["designation"] == "Mietvertrag Sporthalle"
        assert revisions[1].after["designation"] == "Mietvertrag Sporthalle (neu)"


def test_search_filter_and_validation(environment):
    client, app = environment
    login(client, "admin")
    create_contract(client, "1", "Sporthalle")
    create_contract(client, "2", "Büroflächen")
    assert "Sporthalle" in client.get("/?q=Sport").text
    assert "Büroflächen" not in client.get("/?q=Sport").text
    assert "Büroflächen" in client.get("/?department=2").text
    assert "Sporthalle" not in client.get("/?department=2").text
    page = client.get("/contracts/new")
    values = contract_payload(designation="")
    values["csrf_token"] = csrf_from(page.text)
    assert client.post("/contracts/new", data=values).status_code == 422
    values["designation"] = "X" * 201
    assert client.post("/contracts/new", data=values).status_code == 422
    values["designation"] = "Ok"
    values["department_id"] = "999"
    assert client.post("/contracts/new", data=values).status_code == 422


def test_bad_password_and_headers_and_logout(environment):
    client, app = environment
    page = client.get("/login")
    failure = client.post("/login", data={"username": "admin", "password": "not-it",
                                          "csrf_token": csrf_from(page.text)})
    assert failure.status_code == 401
    assert login(client, "admin").status_code == 303
    response = client.get("/")
    assert response.headers["x-frame-options"] == "DENY"
    assert "no-store" in response.headers["cache-control"]
    csrf = csrf_from(response.text)
    logout = client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)
    assert logout.status_code == 303
    assert client.get("/", follow_redirects=False).status_code == 303


def test_xss_escaped_in_html(environment):
    client, app = environment
    login(client, "admin")
    id_x = create_contract(client, designation='<img src=x onerror=alert(1)>')
    assert '<img src=x onerror=alert(1)>' not in client.get("/").text
    assert '&lt;img' in client.get(f"/contracts/{id_x}").text


def test_rate_limit(environment):
    client, app = environment
    page = client.get("/login")
    token = csrf_from(page.text)
    for i in range(8):
        response = client.post("/login", data={"username": "wrong", "password": "bad", "csrf_token": token})
        assert response.status_code == 401
    locked = client.post("/login", data={"username": "wrong", "password": "bad", "csrf_token": token})
    assert locked.status_code == 429


def test_other_department_cannot_mutate_existing_records(environment):
    client, app = environment
    login(client, "admin")
    protected_id = create_contract(client, "2", "Nur Bauamt")
    client.post("/logout", data={"csrf_token": csrf_from(client.get("/").text)})
    login(client, "kultur")
    token = csrf_from(client.get("/").text)
    posted = contract_payload(department_id="1", designation="Unerlaubte Änderung")
    posted.update(csrf_token=token, version="1")
    assert client.post(f"/contracts/{protected_id}/edit", data=posted).status_code == 404
    assert client.post(f"/contracts/{protected_id}/archive", data={"csrf_token": token, "version": "1"}).status_code == 404
    with app.state.session_factory() as db:
        contract = db.get(Contract, protected_id)
        assert contract.designation == "Nur Bauamt"
        assert contract.archived_at is None


def test_database_foreign_keys_enabled(environment):
    client, app = environment
    from sqlalchemy import text
    with app.state.engine.connect() as conn:
        if conn.dialect.name == "sqlite":
            assert conn.scalar(text("PRAGMA foreign_keys")) == 1
        else:
            from sqlalchemy import inspect
            assert inspect(conn).get_foreign_keys("contracts")
