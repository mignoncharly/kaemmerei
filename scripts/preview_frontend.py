"""Local synthetic preview. Never connects to an existing business database.

python scripts/preview_frontend.py --port 8766 [--empty]
The fixtures and synthetic scanner exist only for this disposable process.
"""
import argparse
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--empty', action='store_true')
    args = parser.parse_args()
    import uvicorn
    from tests.support import environment_context, login, create_contract, PASSWORD
    from app.models import Contract, ContactIdentity, ContractTask, ContractReview, RecipientTeam, RecipientMembership, User
    from sqlalchemy import select
    with environment_context('sqlite') as (client, app):
        with app.state.session_factory() as db:
            db.add(ContactIdentity(display_name='Dienststelle', department_id=1, scope_key=1, is_active=True))
            db.commit()
        if not args.empty:
            login(client, 'admin')
            contracts = [create_contract(client, designation=title, department_id=department)
                         for title, department in [('SYNTHETISCH | Nutzung der Sporthalle', '1'),
                             ('SYNTHETISCH | Wartung Veranstaltungstechnik', '1'),
                             ('SYNTHETISCH | Reinigung Bürgerhaus', '1'),
                             ('SYNTHETISCH | Bauhof-Gerätemiete', '2')]]
            with app.state.session_factory() as db:
                reviewer = db.scalar(select(User).where(User.username == 'pruefer'))
                reviewer.can_approve = True
                team = RecipientTeam(name='Synthetische Prüfstelle', is_active=True)
                db.add(team); db.flush()
                db.add(RecipientMembership(team_id=team.id, user_id=reviewer.id))
                for index, cid in enumerate(contracts):
                    contract = db.get(Contract, cid)
                    contract.end_date = date.today() + timedelta(days=25 + index*30)
                    contract.notice_period_months = 1
                    db.add(ContractTask(contract_id=cid, title='Unterlagen auf Vollständigkeit prüfen',
                        kind='review', status='open', description='Ausschließlich synthetischer Testvorgang.',
                        due_date=date.today()+timedelta(days=7), assigned_user_id=2 if index<3 else 3,
                        created_by_id=1))
                db.add(ContractReview(contract_id=contracts[0], recipient=team.name,
                    subject='Synthetische Vollständigkeitsprüfung', status='open', request_text='Unterlagen prüfen.',
                    result_text='', created_by_id=1, assigned_user_id=reviewer.id, team_id=team.id,
                    content_revision=1, due_date=date.today()+timedelta(days=4)))
                db.commit()
        print(f'Synthetic preview: http://localhost:{args.port}', flush=True)
        print('Accounts: admin / kultur / bau / pruefer', flush=True)
        print(f'Synthetic password: {PASSWORD}', flush=True)
        print('Disposable SQLite; synthetic scanner; no production configuration changed. Stop with Ctrl+C.', flush=True)
        uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning', access_log=False)

if __name__ == '__main__':
    main()
