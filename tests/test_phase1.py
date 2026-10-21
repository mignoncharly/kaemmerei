from tests.support import workflow_payload
"""Phase 1 verification. Runs under unittest or pytest, with real migrations."""
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from sqlalchemy import MetaData, Table, inspect, select, text

from app.config import Settings, get_settings
from app.db import make_engine
from app.migrations import migration_head, upgrade_connection
from app.models import Contract, Department, IntegrationToken, now_utc
from app.security import hash_value
from tests.support import (create_contract, csrf_from, disposable_database,
                           environment_context, login, scratch_directory)


def backend():
    return os.environ.get("VERIFICATION_DATABASE", "sqlite")


class ConfigurationTests(unittest.TestCase):
    def test_postgresql_fixture_rejects_unsafe_targets_before_connecting(self):
        with scratch_directory(prefix="ohvr-config-") as directory:
            for target in (None, "postgresql+psycopg://user@remote.invalid/postgres",
                           "postgresql+psycopg://user@127.0.0.1/business",
                           "sqlite:///regular.sqlite3",
                           "postgresql+psycopg://user@127.0.0.1/postgres?service=unexpected"):
                with self.subTest(target=target), patch.dict(os.environ):
                    if target is None:
                        os.environ.pop("TEST_POSTGRES_ADMIN_URL", None)
                    else:
                        os.environ["TEST_POSTGRES_ADMIN_URL"] = target
                    with self.assertRaises((ValueError, RuntimeError)):
                        with disposable_database("postgresql", Path(directory)):
                            self.fail("Unsafe target reached a fixture body")

    def test_unsafe_production_configuration_fails_before_connection(self):
        with scratch_directory(prefix="ohvr-config-") as directory:
            for values in (
                {"environment": "invalid"},
                {"allowed_hosts": ()},
                {"allowed_hosts": ("*",)},
                {"environment": "production", "allowed_hosts": ("register.example.invalid",)},
                {"environment": "production", "database_url": "postgresql+psycopg://invalid/unused",
                 "allowed_hosts": ("localhost",)},
                {"environment": "production", "database_url": "postgresql+psycopg://invalid/unused",
                 "allowed_hosts": ("testserver",)},
            ):
                with self.subTest(values=values), self.assertRaises(ValueError):
                    Settings(**values, document_storage_dir=Path(directory) / "documents").validate()

    def test_document_environment_is_read_per_configuration(self):
        with scratch_directory(prefix="ohvr-config-") as directory:
            root = Path(directory)
            env = {"APP_ENV": "development", "DATABASE_URL": f"sqlite:///{root / 'db.sqlite3'}",
                   "ALLOWED_HOSTS": "localhost", "DOCUMENT_STORAGE_DIR": str(root / "first")}
            with patch.dict(os.environ, env):
                first = get_settings()
                os.environ["DOCUMENT_STORAGE_DIR"] = str(root / "second")
                second = get_settings()
            self.assertEqual(first.document_storage_dir, (root / "first").resolve())
            self.assertEqual(second.document_storage_dir, (root / "second").resolve())
            self.assertFalse((root / "db.sqlite3").exists())


class MigrationTests(unittest.TestCase):
    def check_upgrade(self, populated):
        with scratch_directory(prefix="ohvr-migration-") as directory:
            with disposable_database(backend(), Path(directory)) as url:
                engine = make_engine(Settings(database_url=url))
                try:
                    with engine.connect() as connection:
                        if populated:
                            upgrade_connection(connection, "0001_initial")
                            schema = MetaData()
                            tables = {name: Table(name, schema, autoload_with=connection)
                                      for name in ("departments", "users", "contracts", "revisions")}
                            stamp = datetime(2025, 1, 15, 10, 0)
                            connection.execute(tables["departments"].insert(), {"id": 1, "name": "Synthetic", "is_active": True})
                            connection.execute(tables["users"].insert(), {
                                "id": 1, "username": "synthetic", "password_hash": "not-a-login-hash",
                                "role": "admin", "is_active": True, "created_at": stamp})
                            connection.execute(tables["contracts"].insert(), {
                                "id": 1, "designation": "Preserved synthetic record", "contract_type": "Miete",
                                "relevant_date": date(2025, 1, 1), "date_description": "Beginn",
                                "department_id": 1, "contact_person": "Synthetic contact", "created_by_id": 1,
                                "updated_by_id": 1, "created_at": stamp, "updated_at": stamp, "version": 3})
                            connection.execute(tables["revisions"].insert(), {
                                "id": 1, "contract_id": 1, "actor_id": 1, "action": "created",
                                "before": None, "after": {"designation": "Preserved synthetic record"}, "created_at": stamp})
                            connection.commit()
                            upgrade_connection(connection, "0003_contract_documents")
                            documents = Table("contract_documents", MetaData(), autoload_with=connection)
                            connection.execute(documents.insert(), {
                                "id": 1, "contract_id": 1, "uploaded_by_id": 1,
                                "original_filename": "synthetic.pdf", "storage_key": "a" * 32 + ".pdf",
                                "size_bytes": 12, "uploaded_at": stamp})
                            connection.commit()
                        upgrade_connection(connection)
                        self.assertEqual(connection.scalar(text("SELECT version_num FROM alembic_version")), migration_head())
                        self.assertTrue({"contracts", "contract_documents", "contract_tasks", "contract_reviews",
                                         "integration_tokens", "revisions"}.issubset(inspect(connection).get_table_names()))
                        if populated:
                            row = connection.execute(select(Contract.__table__)).mappings().one()
                            self.assertEqual(row["designation"], "Preserved synthetic record")
                            self.assertEqual(row["contract_number"], "VR-2025-0001")
                            self.assertEqual(row["version"], 3)
                            self.assertEqual(connection.scalar(text("SELECT count(*) FROM revisions")), 1)
                            self.assertEqual(connection.scalar(text("SELECT original_filename FROM contract_documents")), "synthetic.pdf")
                            self.assertEqual(connection.scalar(text("SELECT content_type FROM contract_documents")), "application/pdf")
                            legacy=connection.execute(text('SELECT state,scan_result,provenance,sha256,scanner_version,scanned_at,legal_hold,retention_class FROM contract_documents')).one()
                            self.assertEqual(tuple(legacy[:3]),('legacy_unverified','unverified','legacy_unverified'))
                            self.assertEqual(tuple(legacy[3:6]),(None,None,None))
                            self.assertFalse(legacy[6])
                            self.assertEqual(legacy[7],'unclassified')
                        connection.commit()
                        upgrade_connection(connection)  # Head is idempotent.
                finally:
                    engine.dispose()

    def test_clean_upgrade(self):
        self.check_upgrade(False)

    def test_populated_initial_upgrade_preserves_records_and_document_metadata(self):
        self.check_upgrade(True)


class ResourceAndPermissionTests(unittest.TestCase):
    def test_upload_preview_download_and_api_use_instance_storage(self):
        with environment_context(backend()) as (client, app):
            login(client, "admin")
            contract_id = create_contract(client)
            token = csrf_from(client.get(f"/contracts/{contract_id}").text)
            content = b"%PDF-1.4\nsynthetic verification document\n%%EOF"
            response = client.post(f"/contracts/{contract_id}/documents", data=workflow_payload(client,f"/contracts/{contract_id}/documents",{"csrf_token": token}),
                                   files={"documents": ("synthetic.pdf", content, "application/pdf")}, follow_redirects=False)
            self.assertEqual(response.status_code, 303, response.text)
            from app.models import ContractDocument
            with app.state.session_factory() as db:
                document = db.scalar(select(ContractDocument))
                doc_id, key = document.id, document.storage_key
                credential = "ohvr_" + "S" * 32
                db.add(IntegrationToken(name="Synthetic", token_prefix=credential[:16], token_hash=hash_value(credential),
                                        department_id=1, created_by_id=1))
                db.commit()
            self.assertEqual((app.state.document_storage_dir / 'blobs' / key).read_bytes(), content)
            path = f"/contracts/{contract_id}/documents/{doc_id}"
            self.assertEqual(client.get(path).content, content)
            self.assertIn("attachment", client.get(path + "?download=1").headers["content-disposition"])
            self.assertEqual(client.get("/api/v1" + path, headers={"Authorization": "Bearer " + credential}).content, content)
            with environment_context(backend()) as (other_client, other_app):
                self.assertNotEqual(app.state.document_storage_dir, other_app.state.document_storage_dir)
                login(other_client, "admin")
                create_contract(other_client)
                self.assertEqual(other_client.get(path).status_code, 404)
                self.assertFalse((other_app.state.document_storage_dir / 'blobs' / key).exists())

    def test_inactive_user_cannot_login(self):
        with environment_context(backend()) as (client, app):
            self.assertEqual(login(client, "inactive").status_code, 401)
            self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)

    def test_parent_and_child_ownership_and_reviewer_mutation_denial(self):
        with environment_context(backend()) as (client, app):
            login(client, "admin")
            first = create_contract(client, "1", "First")
            second = create_contract(client, "2", "Second")
            token = csrf_from(client.get("/").text)
            response = client.post(f"/contracts/{second}/tasks", data=workflow_payload(client,f"/contracts/{second}/tasks",{"csrf_token": token, "title": "Synthetic task", "kind": "review"}), follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            from app.models import ContractTask
            with app.state.session_factory() as db:
                task_id = db.scalar(select(ContractTask.id))
            # A child ID cannot be moved to a different parent, even by an admin.
            response = client.post(f"/contracts/{first}/tasks/{task_id}", data=workflow_payload(client,f"/contracts/{first}/tasks/{task_id}",{"csrf_token": token}))
            self.assertEqual(response.status_code, 404)
            client.post("/logout", data={"csrf_token": token})
            login(client, "kultur")
            token = csrf_from(client.get("/").text)
            for endpoint in (f"/contracts/{second}/tasks", f"/contracts/{second}/reviews",
                             f"/contracts/{second}/documents", f"/contracts/{second}/documents/link"):
                self.assertEqual(client.post(endpoint, data=workflow_payload(client,endpoint,{"csrf_token": token})).status_code, 404)
            client.post("/logout", data={"csrf_token": token})
            login(client, "pruefer")
            token = csrf_from(client.get("/").text)
            for suffix in ("tasks", "reviews", "documents", "documents/link"):
                self.assertEqual(client.post(f"/contracts/{first}/{suffix}", data={"csrf_token": token}).status_code, 403)

    def test_scoped_unscoped_expired_revoked_and_invalid_api_credentials(self):
        with environment_context(backend()) as (client, app):
            login(client, "admin")
            first, second = create_contract(client, "1", "First"), create_contract(client, "2", "Second")
            credentials = {}
            with app.state.session_factory() as db:
                for index, (name, scope, active, expired) in enumerate((
                    ("scoped", 1, True, False), ("global", None, True, False),
                    ("revoked", None, False, False), ("expired", None, True, True),
                )):
                    raw = "ohvr_" + str(index) * 32
                    credentials[name] = raw
                    db.add(IntegrationToken(name=name, token_prefix=raw[:16], token_hash=hash_value(raw),
                                            department_id=scope, created_by_id=1, is_active=active,
                                            expires_at=now_utc() - timedelta(days=1) if expired else None))
                db.commit()
            for name, raw in credentials.items():
                response = client.get("/api/v1/contracts", headers={"Authorization": "Bearer " + raw})
                if name in ("revoked", "expired"):
                    self.assertEqual(response.status_code, 401)
                else:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual({item["id"] for item in response.json()["data"]},
                                     {first} if name == "scoped" else {first, second})
            self.assertEqual(client.get("/api/v1/contracts").status_code, 401)
            self.assertEqual(client.get("/api/v1/contracts", headers={"Authorization": "Bearer ohvr_invalid"}).status_code, 401)


class SecurityRegressionTests(unittest.TestCase):
    """Passing regressions for the three original acceptance security defects."""
    def setUp(self):
        # Migration, setup and transport failures must remain real errors.
        client, app = self.enterContext(environment_context(backend()))
        self.assertEqual(login(client, "admin").status_code, 303)
        if "R01" in self._testMethodName:
            record_id = create_contract(client, "2", "Private")
            with app.state.session_factory() as db:
                db.get(Contract, record_id).contract_type = "DEPARTMENT_B_PRIVATE_TYPE"
                db.commit()
            client.post("/logout", data={"csrf_token": csrf_from(client.get("/").text)})
            self.assertEqual(login(client, "kultur").status_code, 303)
            self.response = client.get("/")
            self.assertEqual(self.response.status_code, 200)
        elif "R04" in self._testMethodName:
            record_id = create_contract(client)
            token = csrf_from(client.get("/").text)
            created = client.post(f"/contracts/{record_id}/reviews", data=workflow_payload(client,f"/contracts/{record_id}/reviews",{"csrf_token": token,
                        "recipient": "Kämmerei", "subject": "Synthetic review"}), follow_redirects=False)
            self.assertEqual(created.status_code, 303)
            from app.models import ContractReview
            with app.state.session_factory() as db:
                review_id = db.scalar(select(ContractReview.id))
            archived = client.post(f"/contracts/{record_id}/archive", data={"csrf_token": token, "version": "1"}, follow_redirects=False)
            self.assertEqual(archived.status_code, 303)
            self.response = client.post(f"/contracts/{record_id}/reviews/{review_id}",
                                   data=workflow_payload(client,f"/contracts/{record_id}/reviews/{review_id}",{"csrf_token": token, "status": "approved", "result_text": "Synthetic"}), follow_redirects=False)
        elif "R10" in self._testMethodName:
            client.post("/logout", data={"csrf_token": csrf_from(client.get("/").text)})
            self.assertEqual(login(client, "kultur").status_code, 303)
            with app.state.session_factory() as db:
                db.get(Department, 1).is_active = False
                db.commit()
            self.response = client.get("/", follow_redirects=False)

    def test_R01_cross_department_metadata_is_not_visible(self):
        self.assertNotIn("DEPARTMENT_B_PRIVATE_TYPE", self.response.text)

    def test_R04_archived_reviews_are_immutable(self):
        self.assertEqual(self.response.status_code, 409)

    def test_R10_inactive_department_denies_access(self):
        self.assertEqual(self.response.status_code, 303)


def load_tests(loader, tests, pattern):
    """Run the original test functions unchanged through real unittest cases.

    Pytest collects those functions normally. This adapter is for the stdlib
    runner when pytest cannot be installed; it is not a replacement pytest shim.
    """
    from tests import test_app
    for name in sorted(dir(test_app)):
        if name.startswith("test_"):
            function = getattr(test_app, name)
            def execute(function=function):
                with environment_context(backend()) as environment:
                    function(environment)
            tests.addTest(unittest.FunctionTestCase(execute, description=name))
    return tests
