# Sistema de Relatórios - Open Monitor

## Visão Geral

O Sistema de Relatórios do Open Monitor é uma solução completa e robusta para geração, personalização e distribuição de relatórios de segurança cibernética. O sistema oferece funcionalidades avançadas incluindo análise por IA, exportação em múltiplos formatos, sistema de notificações, cache inteligente e configurações personalizáveis.

## Arquitetura do Sistema

### Componentes Principais

1. **Controller Principal** (`controllers/report_controller.py`)
   - Gerencia todas as rotas e endpoints
   - Coordena a interação entre serviços
   - Implementa autenticação e autorização

2. **Serviços Core**
   - `ReportDataService`: Compilação e processamento de dados
   - `ReportAIService`: Análises inteligentes e insights
   - `PDFExportService`: Exportação para PDF e DOCX
   - `ReportBadgeService`: Sistema de badges e tags
   - `ReportNotificationService`: Notificações multi-canal
   - `ReportConfigService`: Configurações personalizáveis
   - `ReportCacheService`: Cache e otimizações

3. **Templates e UI**
   - Templates HTML responsivos
   - Componentes JavaScript interativos
   - Estilos CSS customizáveis

## Funcionalidades

### 1. Geração de Relatórios

#### Tipos de Relatórios Suportados
- **VULNERABILITY**: Relatórios de vulnerabilidades
- **COMPLIANCE**: Relatórios de conformidade
- **RISK_ASSESSMENT**: Avaliações de risco
- **EXECUTIVE**: Relatórios executivos
- **TECHNICAL**: Relatórios técnicos detalhados

#### Níveis de Detalhamento
- **SUMMARY**: Resumo executivo
- **DETAILED**: Análise detalhada
- **COMPREHENSIVE**: Análise completa com todos os dados

#### Escopo de Análise
- **ORGANIZATION**: Toda a organização
- **DEPARTMENT**: Departamento específico
- **PROJECT**: Projeto específico
- **ASSET_GROUP**: Grupo de ativos
- **CUSTOM**: Escopo personalizado

### 2. Análise por Inteligência Artificial

O sistema integra análises avançadas por IA que incluem:

- **Resumo Executivo**: Síntese inteligente dos principais achados
- **Análise de Impacto**: Avaliação do impacto nos negócios
- **Plano de Remediação**: Recomendações priorizadas de correção
- **Análise Técnica**: Insights técnicos detalhados
- **Predições de Tendências**: Análise preditiva de riscos

### 3. Sistema de Exportação

#### Formatos Suportados
- **PDF**: Relatórios profissionais com formatação avançada
- **DOCX**: Documentos editáveis do Microsoft Word
- **HTML**: Visualização web interativa
- **JSON**: Dados estruturados para integração

#### Características da Exportação PDF
- Cabeçalhos e rodapés personalizáveis
- Marca d'água e branding corporativo
- Gráficos e visualizações de alta qualidade
- Índice automático e navegação
- Metadados e propriedades do documento

### 4. Sistema de Badges e Tags

#### Badges Automáticos
- **CRITICAL_SECURITY**: Vulnerabilidades críticas detectadas
- **COMPLIANCE_READY**: Pronto para auditoria de conformidade
- **HIGH_COVERAGE**: Alta cobertura de ativos
- **AI_ENHANCED**: Relatório com análise de IA
- **EXECUTIVE_SUMMARY**: Inclui resumo executivo
- **TREND_ANALYSIS**: Análise de tendências incluída

#### Tags Inteligentes
- Tags baseadas em conteúdo do relatório
- Categorização automática por tipo de vulnerabilidade
- Tags de conformidade (ISO 27001, NIST, etc.)
- Tags de criticidade e prioridade

### 5. Sistema de Notificações

#### Canais Suportados
- **Email**: Notificações por email com templates HTML
- **Slack**: Integração com workspaces Slack
- **Microsoft Teams**: Notificações em canais Teams
- **Discord**: Webhooks para servidores Discord
- **SMS**: Mensagens de texto para alertas críticos
- **Push**: Notificações push para aplicativos móveis
- **Webhook**: Integrações personalizadas via HTTP

#### Eventos de Notificação
- **report_created**: Relatório criado
- **report_completed**: Relatório concluído
- **report_failed**: Falha na geração
- **critical_vulnerabilities_found**: Vulnerabilidades críticas detectadas

#### Prioridades
- **LOW**: Notificações informativas
- **MEDIUM**: Notificações importantes
- **HIGH**: Notificações urgentes
- **CRITICAL**: Alertas críticos

### 6. Sistema de Configuração

#### Escopos de Configuração
- **GLOBAL**: Configurações do sistema
- **ORGANIZATION**: Configurações da organização
- **USER**: Configurações do usuário
- **REPORT_TYPE**: Configurações por tipo de relatório

#### Categorias de Configuração
- **TEMPLATES**: Templates personalizados
- **EXPORT**: Configurações de exportação
- **NOTIFICATIONS**: Configurações de notificação
- **CHARTS**: Configurações de gráficos
- **AI_ANALYSIS**: Configurações de IA
- **SCHEDULING**: Configurações de agendamento
- **BRANDING**: Configurações de marca
- **SECURITY**: Configurações de segurança

### 7. Sistema de Cache

#### Tipos de Cache
- **Memory Cache**: Cache em memória com LRU
- **Redis Cache**: Cache distribuído
- **Query Cache**: Cache de consultas ao banco
- **Chart Cache**: Cache de dados de gráficos

#### Estratégias de Cache
- TTL (Time To Live) configurável
- Invalidação automática
- Pré-carregamento de dados
- Compressão de dados

## API REST

### Endpoints Principais

#### Relatórios
```
GET    /reports                    # Listar relatórios
POST   /reports                    # Criar relatório
GET    /reports/{id}               # Visualizar relatório
PUT    /reports/{id}               # Atualizar relatório
DELETE /reports/{id}               # Excluir relatório
POST   /reports/{id}/regenerate    # Regenerar relatório
GET    /reports/{id}/export        # Exportar relatório
```

#### API REST
```
GET    /api/reports                # Listar relatórios (JSON)
GET    /api/reports/{id}           # Obter relatório (JSON)
GET    /api/reports/{id}/status    # Status do relatório
GET    /api/reports/{id}/charts    # Dados de gráficos
GET    /api/reports/{id}/badges    # Badges do relatório
```

#### Configurações
```
GET    /api/config/{category}      # Obter configuração
POST   /api/config/{category}      # Definir configuração
GET    /api/config/templates       # Listar templates
POST   /api/config/templates       # Adicionar template
```

#### Notificações
```
GET    /api/notifications/channels # Listar canais
POST   /api/notifications/channels # Adicionar canal
GET    /api/notifications/history  # Histórico de notificações
```

#### Cache
```
GET    /api/cache/stats            # Estatísticas do cache
POST   /api/cache/clear            # Limpar cache
POST   /api/cache/preload          # Pré-carregar cache
```

## Configuração e Instalação

### Dependências

```python
# requirements.txt
reportlab>=3.6.0
python-docx>=0.8.11
jinja2>=3.1.0
redis>=4.0.0
celery>=5.2.0
requests>=2.28.0
```

### Configuração do Redis (Opcional)

```python
# settings/production.py
REDIS_URL = 'redis://localhost:6379/0'
CACHE_TYPE = 'redis'
CACHE_REDIS_URL = REDIS_URL
```

### Configuração de Email

```python
# settings/production.py
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'your-email@gmail.com'
MAIL_PASSWORD = 'your-app-password'
```

### Configuração de Webhooks

```python
# Slack
SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/...'

# Teams
TEAMS_WEBHOOK_URL = 'https://outlook.office.com/webhook/...'

# Discord
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/...'
```

## Uso Básico

### 1. Criando um Relatório Simples

```python
from controllers.report_controller import report_bp
from models.report import Report, ReportType, ReportScope

# Criar relatório via formulário web
# Acesse: /reports/create

# Ou via API
data = {
    'title': 'Relatório de Vulnerabilidades Q1 2024',
    'report_type': 'VULNERABILITY',
    'scope': 'ORGANIZATION',
    'period_start': '2024-01-01',
    'period_end': '2024-03-31',
    'include_charts': True,
    'include_ai_analysis': True
}
```

### 2. Configurando Notificações

```python
# Adicionar canal de email
POST /api/notifications/channels
{
    "type": "email",
    "config": {
        "recipients": ["admin@company.com"],
        "template": "default"
    }
}

# Adicionar canal Slack
POST /api/notifications/channels
{
    "type": "slack",
    "config": {
        "webhook_url": "https://hooks.slack.com/...",
        "channel": "#security-alerts"
    }
}
```

### 3. Personalizando Templates

```python
# Adicionar template personalizado
POST /api/config/templates
{
    "name": "Relatório Executivo Personalizado",
    "type": "executive",
    "content": "<html>...</html>",
    "variables": ["company_name", "period", "summary"]
}
```

## Monitoramento e Logs

### Logs do Sistema

O sistema gera logs detalhados para:
- Criação e geração de relatórios
- Operações de cache
- Envio de notificações
- Erros e exceções
- Auditoria de ações

### Métricas de Performance

- Tempo de geração de relatórios
- Taxa de hit do cache
- Estatísticas de notificações
- Uso de recursos do sistema

## Segurança

### Autenticação e Autorização

- Login obrigatório para todas as operações
- Controle de acesso baseado em usuário
- Auditoria de todas as ações

### Proteção de Dados

- Sanitização de dados de entrada
- Validação de formulários
- Proteção contra CSRF
- Logs de auditoria

### Configurações de Segurança

```python
# Configurações recomendadas
REPORT_MAX_SIZE = 100 * 1024 * 1024  # 100MB
REPORT_ALLOWED_FORMATS = ['pdf', 'docx', 'html', 'json']
CACHE_ENCRYPTION = True
NOTIFICATION_RATE_LIMIT = 100  # por hora
```

## Troubleshooting

### Problemas Comuns

1. **Relatório não gera**
   - Verificar logs de erro
   - Validar dados de entrada
   - Verificar conectividade com banco

2. **Cache não funciona**
   - Verificar configuração do Redis
   - Validar permissões de memória
   - Verificar TTL das chaves

3. **Notificações não enviadas**
   - Verificar configuração de webhooks
   - Validar credenciais de email
   - Verificar rate limits

### Comandos de Diagnóstico

```bash
# Verificar status do cache
curl -X GET /api/cache/stats

# Limpar cache
curl -X POST /api/cache/clear

# Verificar logs
tail -f logs/report_system.log
```

## Roadmap

### Próximas Funcionalidades

- [ ] Agendamento automático de relatórios
- [ ] Dashboard de métricas em tempo real
- [ ] Integração com ferramentas de SIEM
- [ ] Relatórios colaborativos
- [ ] API GraphQL
- [ ] Aplicativo móvel
- [ ] Análise de machine learning avançada

## Contribuição

Para contribuir com o sistema de relatórios:

1. Fork o repositório
2. Crie uma branch para sua feature
3. Implemente testes para novas funcionalidades
4. Siga os padrões de código estabelecidos
5. Submeta um pull request

## Suporte

Para suporte técnico:
- Documentação: `/docs`
- Issues: GitHub Issues
- Email: support@openmonitor.com