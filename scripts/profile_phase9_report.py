"""Opt-in synthetic report profile; fixed operation tags, no SQL/parameter output."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
from time import monotonic
from sqlalchemy import event, select
from app.models import User
from scripts.synthetic_workload import seed_recovery
from tests.runtime_support import runtime_environment
from tests.support import login


def profile():
    samples=defaultdict(list)
    with runtime_environment() as runtime:
        with runtime.owner.state.session_factory() as db:
            actor=db.scalar(select(User.id).where(User.username=='admin'))
        dataset=seed_recovery(runtime.owner,actor)
        assert login(runtime.client,'kultur').status_code==303
        def before(conn,cursor,statement,parameters,context,many):
            context._profile_started=monotonic()
        def after(conn,cursor,statement,parameters,context,many):
            sql=statement.lower()
            kind=next((tag for fragment,tag in (
                ('financial_history','historical_aggregation'),('contract_tasks','tasks'),
                ('contract_reviews','reviews'),('from contracts','contract_population')) if fragment in sql),'identity_and_other')
            samples[kind].append(monotonic()-context._profile_started)
        engine=runtime.app.state.engine
        event.listen(engine,'before_cursor_execute',before)
        event.listen(engine,'after_cursor_execute',after)
        try:
            started=monotonic();response=runtime.client.get('/reports');elapsed=monotonic()-started
            assert response.status_code==200 and response.url.path=='/reports'
        finally:
            event.remove(engine,'before_cursor_execute',before)
            event.remove(engine,'after_cursor_execute',after)
    return dict(source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        scope='One restricted department HTTP report; guarded synthetic 10k contracts/50k documents only',
        dataset=dataset,request_seconds=elapsed,response_bytes=len(response.content),
        database_total_seconds=sum(sum(values) for values in samples.values()),
        operations={kind:dict(queries=len(values),seconds=sum(values),max_seconds=max(values)) for kind,values in samples.items()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Choose a new profile evidence path')
    result=profile()
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
