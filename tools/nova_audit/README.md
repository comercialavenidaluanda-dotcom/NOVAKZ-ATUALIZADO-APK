# NOVA KZ — Python Audit Module

Read-only diagnostic tooling for the NOVA KZ Android + Supabase flow.

## What it checks

1. Android source for Supabase client references.
2. Possible privileged Supabase key exposure.
3. Local/default balance logic, including the historical 1,000 AOA fallback.
4. References to `bank_accounts`.
5. Obvious authentication/ownership linkage around bank account access.
6. Optional live Supabase Auth verification with the supplied user access token.
7. Optional read-only `bank_accounts` query using that authenticated user's JWT.

The module **does not write to Supabase**, change balances, execute payments, alter RLS, or modify users.

## Local source audit

From the repository root:

```bash
python -m pip install -r tools/nova_audit/requirements.txt
python tools/nova_audit/auditor.py --zip nova-kz.zip
```

JSON output:

```bash
python tools/nova_audit/auditor.py --zip nova-kz.zip --json
```

## Live Supabase audit

Use a normal authenticated user's access token. Do not use a service_role/secret key for this user-level RLS test.

Set environment variables outside Git:

```bash
export SUPABASE_URL="https://YOUR_PROJECT_REF.supabase.co"
export SUPABASE_PUBLISHABLE_KEY="YOUR_PUBLISHABLE_OR_LEGACY_ANON_KEY"
export SUPABASE_ACCESS_TOKEN="USER_ACCESS_TOKEN"
python tools/nova_audit/auditor.py --zip nova-kz.zip
```

The script calls `/auth/v1/user` to validate the JWT and then reads `/rest/v1/bank_accounts?select=*` with the same user token. This lets us distinguish:

- login/session failure;
- Data API access failure;
- RLS returning zero rows;
- a bank account row existing but not being owned by the authenticated user;
- a balance column not being obvious.

Secrets and tokens are not printed.

## Exit codes

- `0`: no high/critical findings.
- `1`: high findings.
- `2`: critical findings.

This is a diagnostic layer. Supabase/PostgreSQL remains the financial source of truth.
