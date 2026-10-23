"""Validate versioned domain decision packets; never execute unapproved rules.

This is a requirements boundary, not an accounting/legal/disposal interpreter.
An adopted packet still needs a separately reviewed implementation and regressions.
"""
from datetime import date
import re

DOMAINS = frozenset(('finance', 'deadlines', 'records'))


def validate_packet(packet):
    if set(packet) != {'format','domain','version','supersedes','state','approval','questions','cases'}:
        raise ValueError('Unexpected decision packet fields')
    if packet['format'] != 'ohvr-domain-requirements-v1' or packet['domain'] not in DOMAINS:
        raise ValueError('Unsupported decision packet')
    if type(packet['version']) is not int or packet['version'] < 1:
        raise ValueError('Positive integer version required')
    previous = packet['supersedes']
    if previous is not None and (type(previous) is not int or not 1 <= previous < packet['version']):
        raise ValueError('Supersession must reference an earlier version')
    if packet['state'] not in ('pending','adopted','withdrawn'):
        raise ValueError('Unknown decision state')
    if not isinstance(packet['questions'], list) or not packet['questions']:
        raise ValueError('Explicit domain questions required')
    cases = packet['cases']
    if not isinstance(cases, list) or not cases:
        raise ValueError('Test vectors required')
    identifiers = set()
    for case in cases:
        if set(case) != {'id','inputs','expected','rationale','evidence'}:
            raise ValueError('Each case requires input/output, rationale and evidence')
        if not re.fullmatch('[A-Z]+-[0-9]{3}',case['id']) or case['id'] in identifiers:
            raise ValueError('Unique stable case IDs required')
        identifiers.add(case['id'])
        if not isinstance(case['inputs'],dict):
            raise ValueError('Named manual inputs required')
        if packet['state']=='pending' and (case['expected'] is not None or case['evidence'] is not None):
            raise ValueError('Pending answers must not be invented')
        if packet['state']=='adopted' and (case['expected'] is None or not case['rationale'] or not case['evidence']):
            raise ValueError('Adopted cases require written expected results and provenance')
    approval = packet['approval']
    if packet['state']=='adopted':
        if not isinstance(approval,dict) or set(approval)!={'responsible_role','date','reference'} or not all(approval.values()):
            raise ValueError('Written domain approval provenance required')
        date.fromisoformat(approval['date'])
    elif approval is not None:
        raise ValueError('No implied approval')
    return {'domain':packet['domain'],'version':packet['version'],'state':packet['state'],
            'case_ids':sorted(identifiers),'executable':False}
