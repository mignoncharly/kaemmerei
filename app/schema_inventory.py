"""Structural inventory without reading business values or credential contents."""
from sqlalchemy import inspect
from app.db import Base
from app import models  # register metadata


def compare_schema(connection):
    inspector=inspect(connection)
    differences=[]
    existing_tables=set(inspector.get_table_names())
    for name,table in Base.metadata.tables.items():
        if name not in existing_tables:
            differences.append({'table':name,'issue':'missing_table'})
            continue
        actual={c['name']:c for c in inspector.get_columns(name)}
        expected={c.name:c for c in table.columns}
        if set(actual)!=set(expected):
            differences.append({'table':name,'columns':sorted(set(actual)^set(expected))})
        for column in set(actual)&set(expected):
            if (actual[column]['type'].compile(dialect=connection.dialect)!=expected[column].type.compile(dialect=connection.dialect) or
                    actual[column]['nullable']!=expected[column].nullable):
                differences.append({'table':name,'column':column,'issue':'type_or_nullability'})
        foreign={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns']),f.get('options',{}).get('ondelete')) for f in inspector.get_foreign_keys(name)}
        desired={(tuple(c.name for c in f.columns),f.referred_table.name,tuple(e.column.name for e in f.elements),f.ondelete) for f in table.foreign_key_constraints}
        if foreign!=desired:
            differences.append({'table':name,'issue':'foreign_keys','actual':sorted(map(str,foreign)),'expected':sorted(map(str,desired))})
        checks={c['name'] for c in inspector.get_check_constraints(name)}
        desired_checks={c.name for c in table.constraints if c.__class__.__name__=='CheckConstraint'}
        if checks!=desired_checks:
            differences.append({'table':name,'issue':'checks','actual':sorted(checks),'expected':sorted(desired_checks)})
        indexes={(tuple(i['column_names']),bool(i['unique'])) for i in inspector.get_indexes(name) if not i.get('duplicates_constraint')}
        expected_indexes={(tuple(c.name for c in i.columns),bool(i.unique)) for i in table.indexes}
        # SQLite reports unique column constraints separately, PostgreSQL may
        # expose their backing indexes. Compare those constraints independently.
        uniques={tuple(c['column_names']) for c in inspector.get_unique_constraints(name)}
        expected_uniques={tuple(c.name for c in u.columns) for u in table.constraints if u.__class__.__name__=='UniqueConstraint'}
        if indexes!=expected_indexes or uniques!=expected_uniques:
            differences.append({'table':name,'issue':'indexes_or_uniques'})
    return differences
