"""Static route inventory. Does not import the app or open a business database."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build():
    rows = []
    for source in sorted((ROOT / 'app').glob('*.py')):
        tree = ast.parse(source.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr in ('get', 'post') and decorator.args
                        and isinstance(decorator.args[0], ast.Constant)):
                    continue
                path = decorator.args[0].value
                text = ast.get_source_segment(source.read_text(encoding='utf-8'), node)
                templates = sorted({n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
                                    and isinstance(n.value, str) and n.value.endswith('.html')})
                rendering = ', '.join(templates) or ('JSON / Datei' if path.startswith(('/api/', '/health/'))
                                                     or path.endswith('.xlsx') or (decorator.func.attr == 'get' and '/documents/' in path)
                                                     else 'Weiterleitung / gemeinsamer Fehlerzustand')
                if path.startswith('/admin/'):
                    access = 'Administration; serverseitige Prüfung'
                elif path.startswith('/api/'):
                    access = 'Integrationstoken / Scope'
                elif path.startswith(('/login', '/health/')):
                    access = 'Öffentlich; bestehende Schutzmaßnahmen'
                elif path.startswith('/account/mfa'):
                    access = 'Ausstehende MFA-Sitzung'
                else:
                    access = 'Persönliche Sitzung; Objekt-/Fachbereichsrechte'
                tests = [p.name for p in (ROOT / 'tests').glob('test_*.py')
                         if path.rstrip('/') and path.split('{')[0] in p.read_text(encoding='utf-8')]
                rows.append(f'| {decorator.func.attr.upper()} `{path}` | `{source.name}:{node.lineno}` / {node.name} | {rendering} | {access} | {", ".join(tests[:6]) or "Indirekte Workflow-Tests; Browsermatrix ergänzen"} |')
    header = '''# Frontend-Routenmatrix

Statisch aus allen Route-Dekoratoren in `app/*.py` erzeugt. GET-Seiten, POST-Aktionen,
Downloads und maschinenlesbare Endpunkte sind vollständig aufgeführt. Testverweise
sind Quelltextzuordnungen, keine Behauptung ausgeführter Tests.

| Methode / URL | Implementierung / Zweck | Rendering | Zugriff | Bestehende Testzuordnung |
|---|---|---|---|---|
'''
    (ROOT / 'docs/FRONTEND_ROUTE_MATRIX.md').write_text(header + '\n'.join(rows) + '\n', encoding='utf-8')
    print(f'{len(rows)} Routen inventarisiert')

if __name__ == '__main__':
    build()
