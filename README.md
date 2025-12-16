# Open‑Monitor

Plataforma de monitoramento e inteligência de vulnerabilidades, construída em Flask, PostgreSQL e Redis, com execução via Docker Compose. Este documento orienta a primeira execução, criação de conta (fluxo root‑first), sincronização inicial da NVD e como usar as principais funcionalidades e APIs.

## Stack e Arquitetura

- Backend: Python 3.11+, Flask (Blueprints, Flask‑Login, Flask‑SQLAlchemy, Flask‑Migrate)
- Banco de dados: PostgreSQL (`postgres_core`, `postgres_public`)
- Cache: Redis
- Execução: Docker Compose (porta da aplicação `4443`)
- Principais módulos: `app/main_startup.py` (factory/guards), `app/controllers/*` (UI/APIs), `app/jobs/*` (sincronização NVD), `app/models/*` (entidades), `app/services/*` (lógica), `app/templates/*` (UI)

## Pré‑requisitos

- Docker e Docker Compose instalados
- Porta `4443` livre na máquina local

## Subir a aplicação (produção local)

1. Clonar o repositório
2. Subir o stack:
   - `docker compose up -d --build`
3. Verificar serviços:
   - `docker compose ps`
   - Logs da app: `docker compose logs -f app`
4. Healthcheck da aplicação (executado automaticamente pelo Compose): `GET /api/v1/system/bootstrap`

Por padrão, a aplicação estará disponível em `http://localhost:4443`.

## Fluxo Root‑First (primeiro acesso)

Antes de qualquer uso, é obrigatório criar o usuário root:

1. Abrir `http://localhost:4443/auth/init-root`
2. Preencher o formulário e enviar
3. O sistema cria o root, salva metadados e redireciona para `/loading`
4. A sincronização inicial da NVD é disparada automaticamente em background

Detalhes do guard e disparo automático estão implementados no factory e controllers.

## Primeira sincronização NVD

- Ao concluir o root, a sincronização completa é iniciada em uma thread daemon
- A página `/loading` exibe progresso em tempo real e redireciona para `/` quando `first_sync_completed=true`
- O progresso pode ser acompanhado via API

APIs relevantes:

- `GET /api/v1/system/bootstrap` — status geral (root e sync)
- `GET /api/v1/sync/progress` — progresso live
- `POST /api/v1/sync/trigger` — força sincronização (completa ou incremental)

Exemplos:

```bash
curl http://localhost:4443/api/v1/system/bootstrap
curl http://localhost:4443/api/v1/sync/progress
curl -X POST http://localhost:4443/api/v1/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

## Criação de conta e autenticação

- Após o root:
  - Usuários podem se registrar em `/auth/register`
  - O fluxo padrão usa confirmação por e‑mail (se configurado) e aprovação do admin
  - Login em `/auth/login`
  - Logout via POST em `/auth/logout`

Durante a sincronização inicial, algumas páginas podem redirecionar para `/loading` para garantir a experiência guiada.

## Principais funcionalidades (UI)

- Home e Overview: contadores de severidade, lista de CVEs recentes, respeitando preferências de vendor
- Vulnerabilidades: busca, filtros, detalhes por `CVE`, severidade, vendors e produtos
- Busca: página de pesquisa rápida com paginação
- Ativos: cadastro de ativos, vinculação a vendors, avaliação de impacto (RTO/RPO)
- Analytics: métricas (top vendors, CWEs, distribuição de severidade, histórico)
- Monitoramento: regras e alertas (dispatcher em `jobs/monitoring_dispatcher.py`)
- Relatórios: geração e exportação (PDF/HTML) com progresso
- Insights e News: feed consolidado e análises

## APIs principais

- `GET /api/v1/cves` — lista paginada de vulnerabilidades
- `GET /api/v1/cves/{cve_id}` — detalhe da vulnerabilidade
- `GET /api/v1/vendors` — lista de vendors
- `GET/POST /api/v1/account/vendor-preferences` — preferências de vendor do usuário
- `GET /api/v1/home/overview` — overview da Home (contadores e recentes)
- `GET /api/v1/risk/{cve_id}` — risco associado
- `POST /api/v1/assets` / `GET /api/v1/assets` — cadastro e listagem de ativos

Todas as APIs seguem os padrões de Blueprint, validações e handlers de erro locais.

## Execução e verificação

- Subir stack: `docker compose up -d --build`
- Healthcheck: `curl http://localhost:4443/api/v1/system/bootstrap`
- Criar root: acessar `http://localhost:4443/auth/init-root`
- Acompanhar loading: `http://localhost:4443/loading`
- Progresso: `curl http://localhost:4443/api/v1/sync/progress`
- Disparo manual: `curl -X POST http://localhost:4443/api/v1/sync/trigger -H "Content-Type: application/json" -d '{"full": true}'`

Para compilação rápida do backend local (útil em desenvolvimento):

```bash
python -m compileall -q app
```

## Configuração via ambiente (Docker Compose)

- Porta: `4443` (`BASE_URL=http://localhost:4443`)
- Banco: `postgres_core`, `postgres_public` com `pg_isready`
- Cache: `redis` com `ping`
- Variáveis principais configuráveis: `SECRET_KEY`, `DATABASE_URL`, `PUBLIC_DATABASE_URL`, `PUBLIC_MODE`, `LOGIN_ENABLED_IN_PUBLIC_MODE`, parâmetros da NVD (`NVD_API_BASE`, `NVD_API_KEY`, `NVD_PAGE_SIZE`, etc.)

## Segurança

- Não armazenar segredos no código; usar variáveis de ambiente
- Inputs sanitizados e limitadores aplicados em rotas sensíveis
- Operações de banco sempre em `app.app_context()` nas threads/jobs

## Encerrar e limpar

- Finalizar stack: `docker compose down -v`

## Próximos passos

- Definir preferências de vendors no perfil para personalizar dashboards
- Criar regras de monitoramento e configurar notificações
- Gerar relatórios e validar KPIs no módulo de Analytics

## Diagramas de Fluxo

```
Fluxo Root‑First

[Primeiro acesso]
      |
      v
[Requisição a rota protegida]
      |
      v
[Verifica usuários ativos]
 (has_active_user = false ou require_root_setup = true)
      |
      v
[Redireciona -> /auth/init-root]
      |
      v
[Cria ROOT]
  - Persiste metadados (SyncMetadata)
  - Gera instance/docker.env
  - Faz login do root
      |
      v
[Redireciona -> /loading]
      |
      v
[Dispara 1ª sincronização NVD]
  - Status: processing / saving
  - Atualiza progresso (current/total)
      |
      v
[first_sync_completed = true]
      |
      v
[Redireciona -> /]
```

```
Loop de Sincronização NVD

[Trigger]
  - Após ROOT (daemon thread)
  - Manual via POST /api/v1/sync/trigger
      |
      v
[Thread run_sync]
  - with app.app_context()
  - Cria event loop
      |
      v
[EnhancedNVDFetcher.sync_nvd]
  - Calcula total
  - Processa páginas em paralelo
  - Upsert em lote (bulk)
  - Atualiza SyncMetadata:
      - nvd_sync_progress_status
      - nvd_sync_progress_current / total
      - nvd_sync_progress_last_cve
      - nvd_first_sync_completed
      |
      v
[UI /loading]
  - Polls /api/v1/sync/progress
  - Mostra barra verde
  - Redireciona para / quando concluído
```

## Troubleshooting

- Healthcheck falhando (container `app` não “healthy”)
  - Verificar `docker compose logs -f app`
  - Checar variáveis `PORT` e mapeamento `4443:4443` no Compose
  - Confirmar Postgres e Redis “healthy”: `docker compose ps`
  - Testar manualmente `curl http://localhost:4443/api/v1/system/bootstrap`

- Não aparece `/auth/init-root`
  - O guard depende de `has_active_user` e `require_root_setup`; se já existe root ativo, você será levado à Home
  - Se o fluxo travar, recrie volumes: `docker compose down -v && docker compose up -d --build`

- Página `/loading` não avança
  - Conferir metadados: `nvd_first_sync_completed`, `nvd_sync_progress_status`
  - Evitar duplicidade: a API bloqueia novos triggers quando `processing`/`saving` (app/controllers/api_controller.py:300-301)
  - Checar conexão com NVD (latência, rate limit). Configure `NVD_API_KEY` se necessário

- Progresso retorna `401/403`
  - `GET /api/v1/sync/progress` permite acesso público apenas antes de finalizar a primeira sincronização
  - Após concluída, autenticação e role admin podem ser exigidas

- Erros de banco na primeira sincronização
  - A API valida/gera tabelas antes de sincronizar e loga o erro (app/controllers/api_controller.py:292-299, 298)
  - Checar permissões e estado dos binds `core` e `public`

- Redis indisponível
  - O cache é opcional; a sincronização e UI funcionam sem Redis, porém com menor desempenho
  - Verifique `docker compose logs -f redis`

- Conflito de porta 4443
  - Fechar processos que usam 4443
  - Alterar porta publicada no Compose ou variável `PORT` da app

- Desenvolvimento local
  - Compilar rápido: `python -m compileall -q app`
  - Script de verificação: `python scripts/verify_endpoints.py`

