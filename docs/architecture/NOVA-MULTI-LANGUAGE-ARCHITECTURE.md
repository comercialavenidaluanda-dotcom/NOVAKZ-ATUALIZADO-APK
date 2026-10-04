# NOVA KZ — Arquitetura Multi-Linguagem

## Objetivo

Definir fronteiras claras entre as linguagens do NOVA KZ para aumentar segurança, auditabilidade e manutenção sem duplicar a autoridade financeira.

## Stack oficial

| Camada | Linguagem | Responsabilidade |
|---|---|---|
| Android | Kotlin | UI Compose, sessão, biometria, navegação e consumo seguro da API |
| Banco | SQL / PostgreSQL | Fonte de verdade financeira, RLS, constraints, RPCs e auditoria |
| Backend | TypeScript | Edge Functions, webhooks, integrações com PSPs/bancos e APIs |
| Auditoria | Python | auditoria de código, reconciliação, relatórios, testes e análise de risco |
| Segurança/performance | C++ | apenas componentes nativos isolados via JNI/NDK quando houver benefício real |

## Regra principal

**O APK nunca é a autoridade financeira.**

O saldo, estado de pagamentos e autorização de operações devem ser determinados no servidor. Kotlin apenas apresenta o estado recebido de uma fonte autorizada.

### Fluxo de saldo

```
Android/Kotlin
   │ Supabase Auth (JWT)
   ▼
PostgreSQL / Data API
   │ RLS: auth.uid() = owner
   ▼
bank_accounts
   │
   ▼
NovaBalance
```

Para operações financeiras sensíveis:

```
Kotlin → Edge Function / RPC controlada → PostgreSQL
                                      ├─ RLS/ownership
                                      ├─ idempotência
                                      ├─ validação de estado
                                      └─ auditoria
```

## Kotlin

Usar para:
- Compose e Design System NOVA.
- Login, recuperação de sessão e logout.
- Biometria como step-up authentication, não como autoridade financeira.
- Armazenamento seguro de tokens usando Android Keystore.
- Leitura de `bank_accounts` através da sessão autenticada.
- Estados de UI: loading, authenticated, expired, error.

Não usar Kotlin/local storage para:
- definir saldo real;
- aprovar pagamentos;
- guardar service_role/secret keys;
- decidir autorização de outro utilizador.

## SQL/PostgreSQL

Responsável por:
- `bank_accounts` e dados financeiros;
- RLS;
- constraints;
- funções/RPCs;
- ledger e operações financeiras;
- idempotência;
- trilho de auditoria.

Políticas devem usar `TO authenticated` + predicado de ownership. UPDATE deve possuir `USING` e `WITH CHECK`.

## TypeScript

Responsável por:
- Edge Functions;
- webhooks BitPay/Intelize/AppyPay/PayPay e futuros parceiros;
- validação de assinaturas de webhook;
- normalização de estados;
- chamadas a APIs externas;
- gestão de segredos exclusivamente no backend.

Segredos nunca devem entrar no APK.

## Python

Responsável por:
- auditoria automatizada;
- reconciliação entre ledger, `bank_accounts` e provedores;
- deteção de discrepâncias;
- relatórios operacionais;
- testes e análise de risco.

Python não deve alterar saldos diretamente em produção sem uma operação explicitamente autorizada e auditada.

## C++

Usar somente quando houver requisito técnico claro, por exemplo:
- primitivas criptográficas ou wrappers nativos avaliados;
- proteção de pequenos segredos temporários;
- operações de performance;
- anti-tamper complementar.

C++ não substitui:
- RLS;
- autenticação;
- autorização server-side;
- Android Keystore;
- validação no PostgreSQL.

## Contratos entre camadas

1. **Auth:** Supabase Auth emite a sessão; o servidor identifica o utilizador pelo JWT.
2. **Ownership:** cada leitura financeira deve estar vinculada ao utilizador autenticado.
3. **Balance:** uma única fonte de verdade; sem fallback financeiro local.
4. **Writes:** operações financeiras passam por RPC/Edge Function controlada.
5. **Secrets:** somente backend/secret manager.
6. **Logs:** nunca registrar PIN, access token, refresh token, service_role, chaves privadas ou IBAN completo.
7. **Ambientes:** SANDBOX, HOMOLOGATION e PRODUCTION isolados.
8. **Idempotência:** pagamentos devem ter uma chave idempotente e transições válidas.
9. **Auditoria:** mudanças financeiras devem deixar trilho verificável.

## Estrutura de referência

```
app/                         # Kotlin / Android
  src/main/java/
  src/main/cpp/              # C++ somente onde necessário

supabase/
  migrations/                # SQL / PostgreSQL
  functions/                 # TypeScript / Edge Functions

tools/
  nova_audit/                # Python
  nova_reconciliation/       # futuro
  nova_risk/                 # futuro

docs/
  architecture/
```

## Ordem de implementação

### Fase 1 — estabilidade
- Corrigir Login → Supabase Auth → sessão.
- Corrigir leitura de `bank_accounts`.
- Remover qualquer saldo financeiro local/fallback.
- Validar RLS e ownership.

### Fase 2 — backend
- Consolidar RPCs financeiras.
- Edge Functions para integrações.
- Segredos fora do APK.
- Idempotência e auditoria.

### Fase 3 — inteligência
- Python para reconciliação e risco.
- Alertas para discrepâncias de saldo/operações.
- Relatórios operacionais.

### Fase 4 — hardening
- C++/NDK somente para componentes comprovadamente necessários.
- App integrity/anti-tamper complementar.
- Testes de segurança e regressão.

## Critério de aceitação

Uma alteração só é considerada concluída quando:
- compila;
- os testes relevantes passam;
- não expõe segredos;
- respeita RLS/ownership;
- não cria uma segunda fonte de verdade financeira;
- possui caminho de rollback/auditoria.
