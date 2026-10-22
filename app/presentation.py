"""Allowlisted noncredential form recovery and normalized checkbox state."""
SAFE_FIELDS = frozenset(('designation','contract_type','contract_partner','relevant_date','end_date',
    'date_description','department_id','contact_person','deputy_contact_person','status',
    'notice_period_months','automatic_renewal','renewal_period_months','contract_value','annual_value',
    'financial_direction','value_basis','external_reference','payment_interval','budget_assignment',
    'tax_review_status','tax_review_result','username','role','is_active','can_approve','title','kind',
    'due_date','description','assigned_user_id','assigned_to','subject','recipient','recipient_detail',
    'request_text','result_text','version','name','display_name','team_id','user_id',
    'service_owner','owner_user_id','expires_in','api_profile','api_scopes','document_name'))
FIELD_LABELS = dict(designation='Bezeichnung',contract_type='Vertragsart',contract_partner='Vertragspartner',
    relevant_date='Vertragsbeginn',end_date='Vertragsende',date_description='Datumsbeschreibung',department_id='Fachbereich',
    contact_person='Zuständige Person',deputy_contact_person='Vertretung',status='Status',notice_period_months='Kündigungsfrist (Monate)',
    automatic_renewal='Automatische Verlängerung',renewal_period_months='Verlängerungszeitraum (Monate)',
    contract_value='Gesamtvertragswert',annual_value='Jahreswert',financial_direction='Einnahme oder Ausgabe',
    value_basis='Wertbasis',external_reference='Externe Referenz',payment_interval='Zahlungsintervall',
    budget_assignment='Haushaltszuordnung',tax_review_status='Steuerlicher Prüfstatus',tax_review_result='Steuerliches Prüfergebnis',
    username='Benutzername',role='Rolle',is_active='Konto aktiv',can_approve='Freigabefähigkeit',title='Titel',kind='Art',
    due_date='Frist',description='Beschreibung',assigned_user_id='Zugewiesenes Konto',assigned_to='Zuständigkeit',
    subject='Betreff',recipient='Prüfstelle',recipient_detail='Empfängerangabe',request_text='Prüfauftrag',
    result_text='Rückmeldung',version='Geladene Version',name='Name',display_name='Anzeigename',team_id='Team',user_id='Konto',
    service_owner='Verantwortlicher Dienst',owner_user_id='Verantwortliches Konto',expires_in='Laufzeit',
    api_profile='API-Profil',api_scopes='API-Rechte',capability='Leserechte',document_name='Dokumentbezeichnung')


def safe_values(form):
    values={k:str(v)[:5000] for k,v in form.items() if k in SAFE_FIELDS and isinstance(v,str)}
    if hasattr(form, 'getlist'):
        allowed = {'metadata','finance','documents','document_content','tax','tasks','history'}
        values['capability'] = ','.join(v for v in form.getlist('capability') if v in allowed)
    for key in ('automatic_renewal','is_active','can_approve'):
        values[key]=str(form.get(key,''))=='1'
    return values


def review_options(user, contract, review, permitted, statuses):
    if not permitted or review.content_revision != contract.content_revision:
        return []
    if review.status in ('approved','changes_requested','rejected','withdrawn'):
        return [(code,label) for code,label in statuses if code=='open'] if user.role=='admin' else []
    independent=(review.assigned_user_id==user.id and review.team_id is not None
                 and user.id not in (contract.created_by_id,contract.material_actor_id))
    return [(code,label) for code,label in statuses if code!='approved' or independent]


def listing_toolbar(filters, page_size, user, departments, focus_labels):
    """Presentation URLs from the existing normalized query; no filtering here."""
    from urllib.parse import urlencode
    from app.options import CONTRACT_STATUSES, TAX_REVIEW_STATUSES
    applied = {key: value for key, value in filters.items() if value}
    if user.role == 'department':
        applied.pop('department', None)  # Ignored by the server for this role.
    paging = {'page_size': page_size} if page_size != 50 else {}
    labels = dict(department='Fachbereich', contract_type='Vertragsart',
                  contact_person='Zuständig', deputy_contact_person='Vertretung',
                  status='Status', tax_review_status='§ 2b UStG', focus='Fokus')
    names = {
        'department': {str(dept.id): dept.name for dept in departments},
        'status': {**dict(CONTRACT_STATUSES), 'archived': 'Archiviert'},
        'tax_review_status': dict(TAX_REVIEW_STATUSES), 'focus': focus_labels,
    }
    def url(values, fragment='contract-toolbar'):
        query = urlencode({**values, **paging})
        return ('/?' + query if query else '/') + '#' + fragment
    chips = [dict(key=key, label=labels[key] + ': ' + names.get(key, {}).get(value, value),
                  remove_url=url({k: v for k, v in applied.items() if k != key}))
             for key, value in applied.items() if key in labels]
    return dict(chips=chips, reset_url=url({'q': applied['q']} if applied.get('q') else {}),
                clear_search_url=url({k: v for k, v in applied.items() if k != 'q'}, 'q'),
                export_url='/contracts/export.xlsx' + ('?' + urlencode(applied) if applied else ''))
