# NOVA KZ — Regras de Fronteira da Stack

## Permitido

- Kotlin → UI, sessão, chamadas autenticadas e apresentação.
- SQL → dados financeiros, RLS, constraints e RPCs.
- TypeScript → Edge Functions, webhooks e integrações.
- Python → auditoria, reconciliação e analytics.
- C++ → componentes nativos pequenos e isolados.

## Proibido

- Service role/secret key no APK.
- Saldo real calculado apenas no dispositivo.
- Aprovação financeira baseada somente em código Kotlin ou C++.
- Python a escrever saldo diretamente em produção como rotina.
- Webhook externo a alterar dados sem validação de assinatura e idempotência.
- Bypass de RLS para resolver erro de aplicação.
- SECURITY DEFINER adicionado apenas para contornar permissões.

## Princípio de mudança

Qualquer novo componente deve declarar:
1. linguagem;
2. camada;
3. dados que lê;
4. dados que escreve;
5. autoridade que possui;
6. mecanismo de autenticação/autorização;
7. estratégia de auditoria;
8. testes e rollback.

A autoridade financeira permanece no PostgreSQL/backend autorizado.
