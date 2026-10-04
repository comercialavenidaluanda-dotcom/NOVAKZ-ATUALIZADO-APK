# NOVA KZ — Remote Runtime Configuration

The Android client reads operational feature flags from `public.nova_runtime_config` after authentication.

## Design rules

- The APK contains feature code, not provider secrets.
- Supabase is the authority for financial state and operational configuration.
- Runtime config is read-only from the mobile client.
- Private credentials remain in Supabase secrets / Edge Functions.
- Changing a supported provider flag, limit, maintenance mode, terms version, or privacy version does not require an APK release.
- New client capabilities that are not already implemented still require an APK release.

## Current production baseline

| Setting | Value |
|---|---|
| environment | production |
| enabled | true |
| maintenance_mode | false |
| Express | false |
| Referência | false |
| IBAN | true |
| KWiK | false |
| NOVA → NOVA | true |
| Minimum transfer | 100 AOA |
| Maximum transfer | 50,000,000 AOA |
| Terms | 1.0 |
| Privacy | 1.2 |

## Security

The table has RLS enabled and only the `authenticated` role can SELECT enabled configurations. There is intentionally no mobile UPDATE policy. Operational changes must be made through a privileged backend/admin path.

## Client contract

The Android repository should expose a typed model such as:

```text
NovaRuntimeConfig
  environment
  configVersion
  maintenanceMode
  expressEnabled
  referenceEnabled
  ibanEnabled
  kwikEnabled
  novaToNovaEnabled
  minTransferAmount
  maxTransferAmount
  termsVersion
  privacyVersion
  defaultCurrency
```

The client must fail closed for payment methods: if a method is absent/disabled, the UI must not offer it.
