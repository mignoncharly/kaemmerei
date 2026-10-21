import pytest
from scripts.benchmark_phase9 import benchmark


@pytest.mark.postgresql
def test_small_actual_mixed_workload_uses_scoped_writes_files_and_history(request):
    if request.config.getoption('--database')!='postgresql':pytest.skip('Actual restricted PostgreSQL workload required')
    result=benchmark(contracts=20,documents=40,users=2,rounds=1,mixed=True)
    assert result['passed'] and result['isolation_passed']
    assert result['dataset']['history']==40 and result['dataset']['actual_files']==40
    assert {x['operation'] for x in result['selections']}=={'dashboard','reports','history_detail','bounded_export','upload_scan','task_create','review_create','login','download'}
