# API REST - Sistema de Relatórios

## Visão Geral

A API REST do Sistema de Relatórios oferece endpoints completos para gerenciar relatórios, configurações, notificações e cache. Todos os endpoints requerem autenticação e seguem os padrões REST.

## Autenticação

Todos os endpoints requerem autenticação via sessão Flask-Login.

```http
Cookie: session=<session_token>
```

## Endpoints de Relatórios

### Listar Relatórios

```http
GET /reports
```

**Parâmetros de Query:**
- `page` (int): Número da página (padrão: 1)
- `per_page` (int): Itens por página (padrão: 10)
- `search` (string): Termo de busca
- `report_type` (string): Filtro por tipo
- `status` (string): Filtro por status
- `date_from` (string): Data inicial (YYYY-MM-DD)
- `date_to` (string): Data final (YYYY-MM-DD)

**Resposta:**
```json
{
  "reports": [
    {
      "id": 1,
      "title": "Relatório de Vulnerabilidades Q1",
      "type": "VULNERABILITY",
      "status": "COMPLETED",
      "created_at": "2024-01-15T10:30:00Z",
      "generated_at": "2024-01-15T10:35:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "pages": 5,
    "per_page": 10,
    "total": 47
  },
  "stats": {
    "total_reports": 47,
    "completed": 42,
    "processing": 3,
    "failed": 2
  }
}
```

### Criar Relatório

```http
POST /reports
```

**Body:**
```json
{
  "title": "Relatório de Vulnerabilidades Q2",
  "description": "Análise trimestral de vulnerabilidades",
  "report_type": "VULNERABILITY",
  "scope": "ORGANIZATION",
  "detail_level": "DETAILED",
  "period_start": "2024-04-01",
  "period_end": "2024-06-30",
  "asset_ids": [1, 2, 3],
  "asset_tags": ["production", "critical"],
  "asset_groups": ["web-servers", "databases"],
  "include_charts": true,
  "chart_types": ["cvss_distribution", "top_assets_risk"],
  "include_ai_analysis": true,
  "ai_analysis_types": ["executive_summary", "remediation_plan"],
  "export_formats": ["pdf", "html"]
}
```

**Resposta:**
```json
{
  "success": true,
  "report": {
    "id": 48,
    "title": "Relatório de Vulnerabilidades Q2",
    "status": "PENDING",
    "created_at": "2024-01-15T14:20:00Z"
  },
  "message": "Relatório criado e geração iniciada com sucesso!"
}
```

### Visualizar Relatório

```http
GET /reports/{id}
```

**Resposta:**
```json
{
  "id": 1,
  "title": "Relatório de Vulnerabilidades Q1",
  "description": "Análise trimestral de vulnerabilidades",
  "type": "VULNERABILITY",
  "scope": "ORGANIZATION",
  "status": "COMPLETED",
  "progress": 100,
  "content": {
    "summary": {
      "total_assets": 150,
      "total_vulnerabilities": 45,
      "critical_vulnerabilities": 3
    }
  },
  "ai_analysis": {
    "executive_summary": "...",
    "business_impact": "...",
    "remediation_plan": "..."
  },
  "chart_data": {
    "cvss_distribution": {...},
    "top_assets_risk": {...}
  },
  "badges": [
    {
      "type": "CRITICAL_SECURITY",
      "label": "Segurança Crítica",
      "color": "red"
    }
  ],
  "tags": [
    {
      "name": "high-priority",
      "color": "orange"
    }
  ]
}
```

### Regenerar Relatório

```http
POST /reports/{id}/regenerate
```

**Resposta:**
```json
{
  "success": true,
  "message": "Regeneração do relatório iniciada com sucesso!"
}
```

### Excluir Relatório

```http
DELETE /reports/{id}
```

**Resposta:**
```json
{
  "success": true,
  "message": "Relatório excluído com sucesso!"
}
```

### Exportar Relatório

```http
GET /reports/{id}/export?format=pdf
```

**Parâmetros de Query:**
- `format` (string): Formato de exportação (pdf, docx, html, json)

**Resposta:**
- Arquivo binário com headers apropriados
- `Content-Type`: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/html, application/json
- `Content-Disposition`: attachment; filename="report_1.pdf"

## API REST JSON

### Listar Relatórios (JSON)

```http
GET /api/reports
```

**Parâmetros de Query:** (mesmos da versão HTML)

**Resposta:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "Relatório de Vulnerabilidades Q1",
      "type": "VULNERABILITY",
      "status": "COMPLETED",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "pages": 5,
    "total": 47
  }
}
```

### Obter Relatório (JSON)

```http
GET /api/reports/{id}
```

**Resposta:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "title": "Relatório de Vulnerabilidades Q1",
    "content": {...},
    "ai_analysis": {...},
    "chart_data": {...}
  }
}
```

### Status do Relatório

```http
GET /api/reports/{id}/status
```

**Resposta:**
```json
{
  "success": true,
  "status": "PROCESSING",
  "progress": 75,
  "estimated_completion": "2024-01-15T10:40:00Z"
}
```

### Dados de Gráficos

```http
GET /api/reports/{id}/charts
```

**Resposta:**
```json
{
  "cvss_distribution": {
    "type": "bar",
    "data": [
      {"label": "Critical", "value": 3},
      {"label": "High", "value": 12},
      {"label": "Medium", "value": 20},
      {"label": "Low", "value": 10}
    ]
  },
  "top_assets_risk": {
    "type": "horizontal_bar",
    "data": [
      {"asset": "web-server-01", "risk_score": 8.5},
      {"asset": "db-server-01", "risk_score": 7.2}
    ]
  }
}
```

### Badges do Relatório

```http
GET /api/reports/{id}/badges
```

**Resposta:**
```json
{
  "badges": [
    {
      "type": "CRITICAL_SECURITY",
      "label": "Segurança Crítica",
      "description": "Vulnerabilidades críticas detectadas",
      "color": "red",
      "icon": "exclamation-triangle"
    }
  ],
  "tags": [
    {
      "name": "high-priority",
      "color": "orange",
      "description": "Alta prioridade"
    }
  ]
}
```

## Endpoints de Configuração

### Obter Configuração

```http
GET /api/config/{category}?scope=USER
```

**Categorias:**
- `templates`
- `export`
- `notifications`
- `charts`
- `ai_analysis`
- `scheduling`
- `branding`
- `security`

**Parâmetros de Query:**
- `scope` (string): GLOBAL, ORGANIZATION, USER, REPORT_TYPE

**Resposta:**
```json
{
  "success": true,
  "config": {
    "default_formats": ["pdf", "html"],
    "auto_export": true,
    "compression": true,
    "watermark": true
  }
}
```

### Definir Configuração

```http
POST /api/config/{category}
```

**Body:**
```json
{
  "scope": "USER",
  "config": {
    "default_formats": ["pdf", "docx"],
    "auto_export": false,
    "compression": true,
    "watermark": false
  }
}
```

**Resposta:**
```json
{
  "success": true,
  "message": "Configuração atualizada com sucesso"
}
```

### Listar Templates

```http
GET /api/config/templates
```

**Resposta:**
```json
{
  "success": true,
  "templates": [
    {
      "id": "default_vulnerability",
      "name": "Relatório de Vulnerabilidades Padrão",
      "type": "vulnerability",
      "description": "Template padrão para relatórios de vulnerabilidades",
      "is_default": true,
      "variables": ["company_name", "period", "summary"]
    }
  ]
}
```

### Adicionar Template

```http
POST /api/config/templates
```

**Body:**
```json
{
  "name": "Template Executivo Personalizado",
  "description": "Template personalizado para relatórios executivos",
  "type": "executive",
  "content": "<html>...</html>",
  "variables": ["company_name", "ceo_name", "period"],
  "is_default": false
}
```

**Resposta:**
```json
{
  "success": true,
  "template": {
    "id": "custom_executive_001",
    "name": "Template Executivo Personalizado",
    "type": "executive"
  }
}
```

## Endpoints de Notificações

### Listar Canais de Notificação

```http
GET /api/notifications/channels
```

**Resposta:**
```json
{
  "success": true,
  "channels": [
    {
      "id": "email_001",
      "type": "email",
      "name": "Email Administrativo",
      "config": {
        "recipients": ["admin@company.com"],
        "template": "default"
      },
      "enabled": true
    },
    {
      "id": "slack_001",
      "type": "slack",
      "name": "Canal Segurança",
      "config": {
        "webhook_url": "https://hooks.slack.com/...",
        "channel": "#security-alerts"
      },
      "enabled": true
    }
  ]
}
```

### Adicionar Canal de Notificação

```http
POST /api/notifications/channels
```

**Body (Email):**
```json
{
  "type": "email",
  "name": "Email Executivo",
  "config": {
    "recipients": ["ceo@company.com", "cto@company.com"],
    "template": "executive",
    "priority": "HIGH"
  }
}
```

**Body (Slack):**
```json
{
  "type": "slack",
  "name": "Canal DevOps",
  "config": {
    "webhook_url": "https://hooks.slack.com/services/...",
    "channel": "#devops-alerts",
    "username": "OpenMonitor",
    "icon_emoji": ":shield:"
  }
}
```

**Body (Webhook):**
```json
{
  "type": "webhook",
  "name": "Sistema SIEM",
  "config": {
    "url": "https://siem.company.com/api/alerts",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer token123",
      "Content-Type": "application/json"
    },
    "timeout": 30
  }
}
```

**Resposta:**
```json
{
  "success": true,
  "channel": {
    "id": "email_002",
    "type": "email",
    "name": "Email Executivo"
  }
}
```

### Histórico de Notificações

```http
GET /api/notifications/history?page=1&per_page=20
```

**Parâmetros de Query:**
- `page` (int): Número da página
- `per_page` (int): Itens por página
- `event` (string): Filtro por evento
- `status` (string): Filtro por status (sent, failed, pending)
- `date_from` (string): Data inicial
- `date_to` (string): Data final

**Resposta:**
```json
{
  "success": true,
  "notifications": [
    {
      "id": "notif_001",
      "event": "report_completed",
      "channel_type": "email",
      "status": "sent",
      "sent_at": "2024-01-15T10:35:00Z",
      "report_id": 1,
      "recipient": "admin@company.com"
    }
  ],
  "pagination": {
    "page": 1,
    "pages": 3,
    "total": 25
  }
}
```

## Endpoints de Cache

### Estatísticas do Cache

```http
GET /api/cache/stats
```

**Resposta:**
```json
{
  "success": true,
  "stats": {
    "memory_cache": {
      "size": 1024,
      "max_size": 10240,
      "hit_rate": 0.85,
      "entries": 150
    },
    "redis_cache": {
      "connected": true,
      "memory_usage": "2.5MB",
      "keys": 300,
      "hit_rate": 0.92
    },
    "query_cache": {
      "cached_queries": 45,
      "hit_rate": 0.78,
      "avg_response_time": "15ms"
    },
    "chart_cache": {
      "cached_charts": 120,
      "hit_rate": 0.88,
      "storage_size": "5.2MB"
    }
  }
}
```

### Limpar Cache

```http
POST /api/cache/clear
```

**Body:**
```json
{
  "type": "all",
  "report_id": null
}
```

**Opções de type:**
- `all`: Limpar todo o cache
- `memory`: Limpar apenas cache em memória
- `redis`: Limpar apenas cache Redis
- `query`: Limpar cache de consultas
- `chart`: Limpar cache de gráficos

**Body (limpar cache específico):**
```json
{
  "type": "report",
  "report_id": 1
}
```

**Resposta:**
```json
{
  "success": true,
  "message": "Cache limpo com sucesso"
}
```

### Pré-carregar Cache

```http
POST /api/cache/preload
```

**Body:**
```json
{
  "report_ids": [1, 2, 3, 4, 5]
}
```

**Resposta:**
```json
{
  "success": true,
  "message": "Cache pré-carregado para 5 relatórios"
}
```

## Códigos de Status HTTP

- `200 OK`: Operação bem-sucedida
- `201 Created`: Recurso criado com sucesso
- `400 Bad Request`: Dados inválidos
- `401 Unauthorized`: Não autenticado
- `403 Forbidden`: Sem permissão
- `404 Not Found`: Recurso não encontrado
- `422 Unprocessable Entity`: Erro de validação
- `500 Internal Server Error`: Erro interno do servidor

## Tratamento de Erros

Todas as respostas de erro seguem o formato:

```json
{
  "success": false,
  "error": "Mensagem de erro",
  "details": {
    "field": "Erro específico do campo"
  }
}
```

## Rate Limiting

A API implementa rate limiting para prevenir abuso:

- **Relatórios**: 100 requests/hora por usuário
- **Notificações**: 50 requests/hora por usuário
- **Cache**: 200 requests/hora por usuário
- **Configurações**: 30 requests/hora por usuário

Headers de rate limiting:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
```

## Webhooks

### Configuração de Webhooks

Para receber notificações via webhook, configure um endpoint que aceite POST requests:

```http
POST https://your-app.com/webhook/openmonitor
Content-Type: application/json
X-OpenMonitor-Signature: sha256=...

{
  "event": "report_completed",
  "timestamp": "2024-01-15T10:35:00Z",
  "data": {
    "report_id": 1,
    "title": "Relatório de Vulnerabilidades Q1",
    "status": "COMPLETED",
    "url": "https://openmonitor.com/reports/1"
  }
}
```

### Verificação de Assinatura

Verifique a assinatura do webhook usando HMAC-SHA256:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## Exemplos de Uso

### Criar e Monitorar Relatório

```javascript
// Criar relatório
const response = await fetch('/reports', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    title: 'Relatório Mensal',
    report_type: 'VULNERABILITY',
    scope: 'ORGANIZATION',
    include_ai_analysis: true
  })
});

const report = await response.json();
const reportId = report.report.id;

// Monitorar progresso
const checkStatus = async () => {
  const statusResponse = await fetch(`/api/reports/${reportId}/status`);
  const status = await statusResponse.json();
  
  if (status.status === 'COMPLETED') {
    console.log('Relatório concluído!');
    // Baixar relatório
    window.location.href = `/reports/${reportId}/export?format=pdf`;
  } else if (status.status === 'PROCESSING') {
    console.log(`Progresso: ${status.progress}%`);
    setTimeout(checkStatus, 5000); // Verificar novamente em 5s
  }
};

checkStatus();
```

### Configurar Notificações

```javascript
// Adicionar canal Slack
await fetch('/api/notifications/channels', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    type: 'slack',
    name: 'Canal Segurança',
    config: {
      webhook_url: 'https://hooks.slack.com/services/...',
      channel: '#security-alerts'
    }
  })
});

// Verificar histórico
const history = await fetch('/api/notifications/history');
const notifications = await history.json();
console.log(notifications.notifications);
```

## Versionamento

A API segue versionamento semântico. A versão atual é v1.

Para futuras versões, use o header:
```http
Accept: application/vnd.openmonitor.v2+json
```