# STRATO suitability investigation — read-only, U022

U023: [the acceptance package](SYNTHETIC_PILOT_ACCEPTANCE.md) adds a non-secret
product/host evidence template and a read-only Windows inventory script. Public
Windows product capability was rechecked; it still establishes no account
entitlement. SFTP access does not prove administrator privileges, native database
installation, persistent ASGI hosting, task registration or VPN/TLS capability.
No account-specific STRATO connector or authorized host endpoint is available;
no secret configuration or website content was inspected or changed.

Conclusion: **the existing account's product and suitability remain unverified**.
No deployment, site/account login, credentials, purchase, DNS/service change or
real municipal data transfer was performed. Windows/PostgreSQL remains the agreed
architecture; no alternative platform is substituted.

Evidence inspected: repository deployment examples (`Caddyfile.example`,
`web-config.example.json`, `Invoke-Ohvr.ps1`) contain placeholder hosts and local
Windows paths, not STRATO product/entitlement evidence. No account secret files
were inspected. The workspace contains this repository and its Python environment;
no separate website checkout was identified at the workspace root.

Public official pages retrieved read-only on 21 October 2026:

- [STRATO hosting capability FAQ](https://www.strato.de/faq/hosting/wie-finde-ich-heraus-welche-technische-unterstuetzungen-zb-php-version-ich-fuer-meine-webinhalte-bei-strato-brauche/)
  describes scripting and MySQL for PowerWeb. Its PHP/MySQL version examples are
  visibly old; they are not a current version inventory or evidence of native
  Windows services/PostgreSQL/ASGI process support for this account.
- [STRATO Dedicated Server Windows](https://www.strato.de/server/windows-dedicated-server/)
  separately advertises Windows Server, administrative access, Task Scheduler,
  firewall and VPN features. This establishes a public product category, **not
  that it has been purchased or configured**. PostgreSQL installation, sustained
  ASGI processes, available capacity and the required network boundary need
  actual-host verification. Provider backup/monitoring marketing is not evidence
  of this application's consistent encrypted recovery or operating acceptance.

Inference: Python or website hosting alone is insufficient to establish suitability.
A separately advertised Windows server could potentially support the architecture;
that inference is conditional on actual product entitlement and host acceptance.

Non-secret evidence needed next: exact product/tariff name and OS category from
an existing order/product overview; authorized read-only technical inventory of
the intended host; ability to administer Windows services/tasks and native
PostgreSQL; storage/capacity; private/VPN firewall design; certificate/database-TLS
capability; isolated backup destination and restore access. Account numbers,
passwords, connection secrets and recovery keys are unnecessary in this report.

| Check | Evidence required before hosted synthetic/user access | Current state |
|---|---|---|
| Isolation from separate website | Separate service identity, paths, ports, storage; reviewed routing | Not inspected |
| Windows/native runtime | OS/build, Python, PostgreSQL/client versions, service supervision | Unverified |
| Internal/VPN boundary | Allowed network, firewall and proxy/TLS test from inside/outside | Unverified |
| PostgreSQL security | Direct restricted roles, RLS, verify-full CA/hostname handshake | Unverified |
| Storage/scanner | Private ACLs, quotas/free space, actual current scanner definitions | Unverified |
| Recovery | Isolated encrypted backup target, custody, scheduled failures/age and restore drill | Unverified |

Do not test these by modifying the current website. The missing product identity
is a hosting dependency; it does not block local engineering or authorize purchase.
