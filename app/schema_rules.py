"""Portable schema invariants and non-destructive legacy inventory."""
from sqlalchemy import text

RULES = {
 'users': {'user_department_consistency': "(role = 'department' AND department_id IS NOT NULL) OR (role IN ('admin','reviewer') AND department_id IS NULL)"},
 'contracts': {
  'valid_contract_status': "status IN ('draft','in_progress','active','terminated','ended')",
  'contract_positive_version': 'version > 0',
  'contract_date_order': 'end_date IS NULL OR end_date >= relevant_date',
  'contract_notice_months': 'notice_period_months IS NULL OR notice_period_months BETWEEN 0 AND 120',
  'contract_renewal_months': 'renewal_period_months IS NULL OR renewal_period_months BETWEEN 1 AND 120',
  'contract_renewal_prerequisites': 'NOT automatic_renewal OR (end_date IS NOT NULL AND renewal_period_months IS NOT NULL)',
  'contract_nonnegative_value': 'contract_value IS NULL OR contract_value >= 0',
  'contract_nonnegative_annual': 'annual_value IS NULL OR annual_value >= 0',
  'contract_direction': "financial_direction IS NULL OR financial_direction IN ('expense','income')",
  'contract_payment_interval': "payment_interval IS NULL OR payment_interval IN ('one_time','monthly','quarterly','semiannual','annual','irregular')",
  'contract_tax_status': "tax_review_status IN ('not_checked','required','in_progress','completed','not_applicable')"},
 'contract_documents': {
  'document_exactly_one_source': '(storage_key IS NOT NULL AND external_url IS NULL) OR (storage_key IS NULL AND external_url IS NOT NULL)',
  'document_nonnegative_size': 'size_bytes >= 0'},
 'contract_reviews': {'review_valid_status': "status IN ('open','in_review','approved','changes_requested','rejected','withdrawn')"},
 'contact_identities': {'contact_scope_consistency': 'scope_key = COALESCE(department_id, 0)'}
}


def inventory(connection):
    """Return only rule names/counts/IDs, never credential or business values."""
    problems = []
    for table, rules in RULES.items():
        for rule, expression in rules.items():
            ids = connection.execute(text(f'SELECT id FROM {table} WHERE NOT ({expression}) ORDER BY id')).scalars().all()
            if ids:
                problems.append({'table': table, 'rule': rule, 'count': len(ids), 'ids': ids})
    ids = connection.execute(text('SELECT c.id FROM contracts c LEFT JOIN users u ON u.id=c.tax_reviewed_by_id '
                                  'WHERE c.tax_reviewed_by_id IS NOT NULL AND u.id IS NULL ORDER BY c.id')).scalars().all()
    if ids:
        problems.append({'table': 'contracts', 'rule': 'missing_tax_reviewer', 'count': len(ids), 'ids': ids})
    return problems
