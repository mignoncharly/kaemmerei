from datetime import date,datetime
from pathlib import Path
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError,IntegrityError
from app.config import Settings
from app.db import make_engine
from app.migrations import upgrade_connection
from app.schema_inventory import compare_schema
from app.schema_rules import inventory
from tests.support import create_contract,login,disposable_database,scratch_directory


def test_schema_inventory_matches_models_and_tax_foreign_key(environment):
    client,app=environment
    login(client,'admin')
    record=create_contract(client)
    with app.state.engine.begin() as connection:
        assert compare_schema(connection)==[]
        assert inventory(connection)==[]
        connection.execute(text('UPDATE contracts SET tax_reviewed_by_id=4 WHERE id=:id'),{'id':record})
        assert connection.scalar(text('SELECT tax_reviewed_by_id FROM contracts WHERE id=:id'),{'id':record})==4
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(text('UPDATE contracts SET tax_reviewed_by_id=999999 WHERE id=:id'),{'id':record})


def test_constraints_reject_invalid_direct_sql(environment):
    client,app=environment
    login(client,'admin')
    record=create_contract(client)
    assignments=["version=0","end_date='2000-01-01'","notice_period_months=-1","notice_period_months=121",
        'renewal_period_months=0','renewal_period_months=121','automatic_renewal=true',
        'contract_value=-1','annual_value=-1',"status='invalid'","financial_direction='invalid'","payment_interval='invalid'",
        "tax_review_status='invalid'"]
    with app.state.engine.begin() as connection:
        for assignment in assignments:
            with pytest.raises(IntegrityError),connection.begin_nested():
                connection.execute(text('UPDATE contracts SET '+assignment+' WHERE id=:id'),{'id':record})
        for statement in ("UPDATE users SET department_id=1 WHERE username='admin'",
                          "UPDATE users SET department_id=NULL WHERE username='kultur'"):
            with pytest.raises(IntegrityError),connection.begin_nested():
                connection.execute(text(statement))
        with pytest.raises(IntegrityError),connection.begin_nested():
            connection.execute(text("INSERT INTO contract_documents(contract_id,uploaded_by_id,original_filename,storage_key,external_url,size_bytes,content_type,uploaded_at) VALUES (:id,1,'synthetic',NULL,NULL,0,'text/plain',:stamp)"),{'id':record,'stamp':'2026-01-01 00:00:00'})


def test_append_only_history_and_audit_cannot_be_modified(environment):
    client,app=environment
    login(client,'admin')
    create_contract(client)
    with app.state.engine.begin() as connection:
        for table in ('revisions','security_events'):
            for statement in (f'UPDATE {table} SET action=action',f'DELETE FROM {table}'):
                with pytest.raises(DBAPIError),connection.begin_nested():
                    connection.execute(text(statement))


def test_invalid_legacy_inventory_aborts_without_silent_repairs(request):
    with scratch_directory('ohvr-phase3-legacy-') as directory:
        with disposable_database(request.config.getoption('--database'),Path(directory)) as target:
            engine=make_engine(Settings(database_url=target))
            try:
                with engine.connect() as connection:
                    upgrade_connection(connection,'0014_identity_authorization')
                    connection.execute(text("INSERT INTO departments(id,name,is_active) VALUES(1,'Synthetic',true)"))
                    connection.execute(text("INSERT INTO users(id,username,password_hash,role,department_id,is_active,created_at) VALUES(1,'synthetic','not-a-credential','admin',1,true,:stamp)"),{'stamp':'2026-01-01 00:00:00'})
                    connection.commit()
                    problems=inventory(connection)
                    assert problems==[{'table':'users','rule':'user_department_consistency','count':1,'ids':[1]}]
                    connection.commit()
                    with pytest.raises(RuntimeError,match='Reviewed legacy repairs'):
                        upgrade_connection(connection)
                    assert connection.scalar(text('SELECT version_num FROM alembic_version'))=='0014_identity_authorization'
                    assert connection.scalar(text('SELECT department_id FROM users WHERE id=1'))==1
                    connection.execute(text('UPDATE users SET department_id=NULL WHERE id=1'))
                    connection.execute(text("INSERT INTO identity_audit(id,actor_id,principal,action,target,details,created_at) VALUES(1,1,'user','password_change_denied','synthetic','{}','2026-01-01 00:00:00')"))
                    connection.commit()
                    upgrade_connection(connection)
                    assert connection.execute(text('SELECT outcome,correlation_id FROM identity_audit WHERE id=1')).one()==('denied',None)
            finally:
                engine.dispose()
