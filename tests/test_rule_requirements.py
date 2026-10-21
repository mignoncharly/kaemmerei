from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.rule_requirements import validate_packet

PACKETS = sorted(Path('docs/rules').glob('*.json'))


@pytest.mark.parametrize('path',PACKETS,ids=lambda p:p.stem)
def test_pending_domain_packets_have_no_invented_expected_results(path):
    result=validate_packet(json.loads(path.read_text(encoding='utf-8')))
    assert result['state']=='pending' and not result['executable']


@pytest.mark.parametrize('fault',['expected','approval','duplicate','supersedes','adopted-without-evidence'])
def test_unapproved_and_incomplete_decisions_are_rejected(fault):
    packet=json.loads(PACKETS[0].read_text(encoding='utf-8'))
    if fault=='expected':packet['cases'][0]['expected']={'invented_total':'100.00'}
    elif fault=='approval':packet['approval']={'reference':'implied'}
    elif fault=='duplicate':packet['cases'].append(deepcopy(packet['cases'][0]))
    elif fault=='supersedes':packet['supersedes']=packet['version']
    else:packet['state']='adopted'
    with pytest.raises(ValueError):validate_packet(packet)
