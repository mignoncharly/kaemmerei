"""Render disabled review-only native task definitions; never register or run.

No credential values belong in task XML. The referenced private JSON/passfiles
must be provisioned separately for each dedicated least-privilege Windows user.
"""
import argparse
from pathlib import Path, PureWindowsPath
import re
import xml.etree.ElementTree as ET

NS = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
ET.register_namespace('', NS)


def local_path(value):
    path = PureWindowsPath(value)
    if (not re.match(r'^[A-Za-z]:\\', value) or not path.is_absolute()
            or any(c in value for c in ('"', '\r', '\n', '<', '>')) or '..' in path.parts):
        raise ValueError('Explicit local Windows paths without traversal are required')
    return str(path)


def task_xml(*, role, python, project, config, account):
    python, project, config = map(local_path, (python, project, config))
    if role not in ('web', 'scan', 'purge', 'reconcile', 'integration-status', 'backup', 'events', 'monitor'):
        raise ValueError('Unsupported scheduled operation')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\\[A-Za-z0-9_.$-]+', account):
        raise ValueError('An explicit DOMAIN\\service-account identity is required')
    def add(parent, tag, value=None, **attrs):
        node = ET.SubElement(parent, '{'+NS+'}'+tag, attrs)
        if value is not None: node.text = value
        return node
    root = ET.Element('{'+NS+'}Task', version='1.4')
    registration = add(root, 'RegistrationInfo')
    add(registration, 'Description', 'OPEN.HERZ review-only '+role+'; disabled until authorized acceptance')
    triggers = add(root, 'Triggers')
    if role == 'web':
        add(add(triggers, 'BootTrigger'), 'Enabled', 'true')
    else:
        trigger = add(triggers, 'CalendarTrigger')
        if role in ('scan', 'purge', 'integration-status', 'backup', 'events', 'monitor'):
            repetition = add(trigger, 'Repetition')
            add(repetition, 'Interval', 'PT2M' if role in ('scan','events','monitor') else 'PT12H' if role=='backup' else 'PT1H')
            add(repetition, 'Duration', 'P1D')
            add(repetition, 'StopAtDurationEnd', 'false')
        add(trigger, 'StartBoundary', '2026-01-01T03:00:00')
        add(trigger, 'Enabled', 'true')
        daily = add(trigger, 'ScheduleByDay')
        add(daily, 'DaysInterval', '1')
    principals = add(root, 'Principals')
    principal = add(principals, 'Principal', id='Operator')
    add(principal, 'UserId', account)
    add(principal, 'LogonType', 'Password')
    add(principal, 'RunLevel', 'LeastPrivilege')
    settings = add(root, 'Settings')
    add(settings, 'MultipleInstancesPolicy', 'IgnoreNew')
    add(settings, 'DisallowStartIfOnBatteries', 'false')
    add(settings, 'StopIfGoingOnBatteries', 'false')
    add(settings, 'StartWhenAvailable', 'true')
    add(settings, 'Enabled', 'false')
    add(settings, 'ExecutionTimeLimit', 'PT0S' if role == 'web' else 'PT70M' if role=='backup' else 'PT10M')
    restart = add(settings, 'RestartOnFailure')
    add(restart, 'Interval', 'PT1M')
    add(restart, 'Count', '10' if role == 'web' else '2')
    actions = add(root, 'Actions', Context='Operator')
    action = add(actions, 'Exec')
    add(action, 'Command', r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')
    wrapper = str(PureWindowsPath(project)/'deploy'/'windows'/'Invoke-Ohvr.ps1')
    add(action, 'Arguments', f'-NoProfile -NonInteractive -WindowStyle Hidden -File "{wrapper}" '
        f'-Role {role} -Python "{python}" -Project "{project}" -Config "{config}"')
    add(action, 'WorkingDirectory', project)
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop('output')
    data = task_xml(**args)
    # No overwrite, registration, account creation or service change.
    with output.open('xb') as stream:
        stream.write(data)
    print('Disabled task definition written; deployment acceptance and registration remain pending.')


if __name__ == '__main__':
    main()
