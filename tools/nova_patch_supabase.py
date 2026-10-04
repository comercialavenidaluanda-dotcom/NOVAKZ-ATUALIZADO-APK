#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
endpoints = next(root.rglob("SupabaseEndpoints.kt"))
client = next(root.rglob("SupabaseRestClient.kt"))

endpoint_text = endpoints.read_text(encoding="utf-8")
client_text = client.read_text(encoding="utf-8")

publishable_key = "sb_publishable_npmGIVLGfRsF8L9UINRnrA_9yqmA7UK"

if "PUBLISHABLE_KEY" not in endpoint_text:
    marker = '    const val PROJECT_REF = "earucsaqqtbllnqsxvlb"'
    replacement = marker + '\n\n    // Supabase publishable key: safe for public Android clients. Never place service_role/secret keys here.\n    const val PUBLISHABLE_KEY = "' + publishable_key + '"'
    if marker not in endpoint_text:
        raise SystemExit("Could not locate SupabaseEndpoints project reference")
    endpoint_text = endpoint_text.replace(marker, replacement, 1)
    endpoints.write_text(endpoint_text, encoding="utf-8")

old = '''                val key = BuildConfig.SUPABASE_ANON_KEY
                if (key.isNullOrBlank() || key.contains("placeholder_anon_key") || key == "NOT_CONFIGURED") "" else key'''
new = '''                val key = BuildConfig.SUPABASE_ANON_KEY
                if (key.isNullOrBlank() || key.contains("placeholder_anon_key") || key == "NOT_CONFIGURED") {
                    SupabaseEndpoints.PUBLISHABLE_KEY
                } else {
                    key
                }'''
if old in client_text:
    client_text = client_text.replace(old, new, 1)
elif "SupabaseEndpoints.PUBLISHABLE_KEY" not in client_text:
    raise SystemExit("Could not locate SupabaseRestClient key resolver")

client_text = client_text.replace(
    'Configuração do Supabase ausente. Defina a SUPABASE_ANON_KEY no painel de segredos',
    'Configuração do Supabase não está disponível no ambiente de build; o APK usa a chave publicável do projeto'
)
client_text = client_text.replace(
    'Defina a chave SUPABASE_ANON_KEY no painel de segredos',
    'o APK usa a chave publicável do projeto'
)
client_text = client_text.replace(
    'Defina a SUPABASE_ANON_KEY no painel de segredos',
    'o APK usa a chave publicável do projeto'
)
client.write_text(client_text, encoding="utf-8")

print(f"Patched: {endpoints}")
print(f"Patched: {client}")
