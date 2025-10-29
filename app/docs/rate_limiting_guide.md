# Sistema de Rate Limiting - Guia de Uso

Este documento descreve o sistema de rate limiting implementado na API do Open Monitor para prevenir abuso e garantir a estabilidade do serviço.

## Visão Geral

O sistema de rate limiting implementado oferece:

- **Rate limiting por IP**: Controla requisições por endereço IP
- **Rate limiting por usuário**: Controla requisições por usuário autenticado
- **Rate limiting por endpoint**: Diferentes limites para diferentes endpoints
- **Configuração flexível**: Limites configuráveis por ambiente
- **Headers informativos**: Headers HTTP com informações sobre limites
- **Whitelist de IPs**: IPs que não sofrem rate limiting
- **Backoff exponencial**: Aumento progressivo do tempo de espera
- **Jitter**: Randomização para evitar thundering herd

## Configuração

### Variáveis de Ambiente

```bash
# Rate limiting geral
RATE_LIMITING_ENABLED=true
RATE_LIMIT_STRATEGY=ip  # ip, user, endpoint
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Rate limiting específico por tipo de endpoint
API_RATE_LIMIT_REQUESTS=60
API_RATE_LIMIT_WINDOW=60

AUTH_RATE_LIMIT_REQUESTS=10
AUTH_RATE_LIMIT_WINDOW=60

SEARCH_RATE_LIMIT_REQUESTS=30
SEARCH_RATE_LIMIT_WINDOW=60

ANALYTICS_RATE_LIMIT_REQUESTS=20
ANALYTICS_RATE_LIMIT_WINDOW=60

ADMIN_RATE_LIMIT_REQUESTS=5
ADMIN_RATE_LIMIT_WINDOW=60

# Headers de rate limiting
RATE_LIMIT_INCLUDE_HEADERS=true

# Whitelist de IPs (separados por vírgula)
RATE_LIMIT_WHITELIST_IPS=192.168.1.100,10.0.0.1

# Redis para rate limiting distribuído (opcional)
USE_REDIS_RATE_LIMITING=false
REDIS_URL=redis://localhost:6379/0
```

### Configuração por Ambiente

O sistema possui configurações específicas para cada ambiente:

#### Desenvolvimento
- Limites mais altos para facilitar desenvolvimento
- Rate limiting menos restritivo
- Logs mais detalhados

#### Produção
- Limites mais baixos para proteção
- Rate limiting mais restritivo
- Logs otimizados

## Limites por Endpoint

### Endpoints Gerais
- **Limite**: 100 requisições por minuto
- **Aplicação**: Endpoints não categorizados

### Endpoints de API (`/api/*`)
- **Limite**: 60 requisições por minuto
- **Aplicação**: Endpoints da API REST

### Endpoints de Autenticação (`/auth/*`, `/api/auth/*`)
- **Limite**: 10 requisições por minuto
- **Aplicação**: Login, logout, registro
- **Motivo**: Prevenção de ataques de força bruta

### Endpoints de Busca (`/search/*`, `/api/search/*`)
- **Limite**: 30 requisições por minuto
- **Aplicação**: Funcionalidades de busca
- **Motivo**: Operações custosas de banco de dados

### Endpoints de Analytics (`/analytics/*`, `/api/analytics/*`)
- **Limite**: 20 requisições por minuto
- **Aplicação**: Dashboards e relatórios
- **Motivo**: Consultas complexas e agregações

### Endpoints Administrativos (`/admin/*`, `/api/admin/*`)
- **Limite**: 5 requisições por minuto
- **Aplicação**: Funcionalidades administrativas
- **Motivo**: Operações sensíveis e críticas

## Headers HTTP

Quando uma requisição é feita, os seguintes headers são incluídos na resposta:

```http
X-RateLimit-Limit: 60          # Limite de requisições por janela
X-RateLimit-Remaining: 45       # Requisições restantes na janela atual
X-RateLimit-Reset: 1640995200   # Timestamp quando a janela reseta
X-RateLimit-Window: 60          # Tamanho da janela em segundos
```

## Códigos de Resposta

### 200 OK
Requisição processada com sucesso dentro do limite.

### 429 Too Many Requests
Limite de rate limiting excedido.

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 30
}
```

## Estratégias de Rate Limiting

### Por IP (`ip`)
- **Padrão**: Controla requisições por endereço IP
- **Uso**: Proteção geral contra abuso
- **Chave**: `ip:192.168.1.100`

### Por Usuário (`user`)
- **Funcionalidade**: Controla requisições por usuário autenticado
- **Uso**: Controle mais granular para usuários logados
- **Chave**: `user:user_id` ou fallback para IP

### Por Endpoint (`endpoint`)
- **Funcionalidade**: Controla requisições por endpoint específico
- **Uso**: Proteção de endpoints específicos
- **Chave**: `endpoint:/api/search`

## Whitelist de IPs

IPs na whitelist não sofrem rate limiting:

- `127.0.0.1` (localhost)
- `::1` (localhost IPv6)
- IPs configurados via `RATE_LIMIT_WHITELIST_IPS`

## Endpoints Isentos

Alguns endpoints são automaticamente isentos de rate limiting:

- `/health` - Health check
- `/static/*` - Arquivos estáticos
- `/favicon.ico` - Favicon
- `/robots.txt` - Robots.txt

## Algoritmo de Rate Limiting

### Sliding Window
O sistema usa o algoritmo de "janela deslizante" que:

1. Mantém registro de timestamps das requisições
2. Remove requisições antigas da janela
3. Verifica se o limite foi excedido
4. Aplica backoff exponencial se necessário

### Backoff Exponencial
Quando o limite é excedido:

1. **Primeira violação**: Espera base (1 segundo)
2. **Violações subsequentes**: Tempo multiplicado por fator (1.5x)
3. **Tempo máximo**: Limitado a 300 segundos
4. **Jitter**: Randomização de ±20% para evitar sincronização

## Monitoramento

### Logs
O sistema registra:

```
2024-01-15 10:30:00 - INFO - Rate limit applied for IP 192.168.1.100: 45/60 requests
2024-01-15 10:30:15 - WARNING - Rate limit exceeded for IP 192.168.1.100: 61/60 requests
2024-01-15 10:30:30 - INFO - Rate limit reset for IP 192.168.1.100
```

### Métricas
Estatísticas disponíveis:

- Total de requisições processadas
- Requisições com rate limiting aplicado
- Tempo médio de espera
- Tempo máximo de espera
- Utilização da janela

## Integração com NVD API

O sistema também inclui rate limiting específico para a API do NVD:

### Sem API Key
- **Limite**: 5 requisições por 30 segundos
- **Backoff**: Mais conservador

### Com API Key
- **Limite**: 50 requisições por 30 segundos
- **Backoff**: Menos restritivo

### Configuração
```python
from utils.rate_limiter import NVDRateLimiter

# Sem API key
rate_limiter = NVDRateLimiter()

# Com API key
rate_limiter = NVDRateLimiter(api_key="sua_api_key")
```

## Testes

### Executar Testes
```bash
# Testar rate limiting da API
python test_api_rate_limiter.py

# Testar rate limiting do NVD
python test_rate_limiter.py
```

### Testes Incluídos
- Rate limiting básico
- Requisições concorrentes
- Diferentes endpoints
- Recuperação após limite
- Backoff exponencial
- Headers HTTP

## Troubleshooting

### Rate Limiting Muito Restritivo
1. Verificar configuração do ambiente
2. Ajustar limites via variáveis de ambiente
3. Adicionar IP à whitelist se necessário

### Rate Limiting Não Funcionando
1. Verificar se `RATE_LIMITING_ENABLED=true`
2. Verificar logs de erro
3. Verificar se IP está na whitelist
4. Verificar se endpoint está isento

### Performance Issues
1. Considerar usar Redis para rate limiting distribuído
2. Ajustar configurações de backoff
3. Otimizar limpeza de dados antigos

## Melhores Práticas

### Para Desenvolvedores
1. **Respeitar headers**: Usar headers de rate limiting para ajustar comportamento
2. **Implementar retry**: Usar backoff exponencial em clientes
3. **Cache**: Implementar cache para reduzir requisições
4. **Batch requests**: Agrupar requisições quando possível

### Para Administradores
1. **Monitorar métricas**: Acompanhar uso e ajustar limites
2. **Configurar alertas**: Alertas para rate limiting excessivo
3. **Whitelist cuidadosa**: Adicionar apenas IPs confiáveis
4. **Logs regulares**: Revisar logs para padrões de abuso

## Configuração Avançada

### Rate Limiting Distribuído com Redis
```python
# Configurar Redis
USE_REDIS_RATE_LIMITING=true
REDIS_URL=redis://localhost:6379/0

# Benefícios:
# - Compartilhamento entre instâncias
# - Persistência de dados
# - Melhor performance em escala
```

### Configuração Personalizada
```python
from utils.api_rate_limiter import FlaskRateLimiter
from config.rate_limiter_config import RateLimiterConfig

# Configuração personalizada
class CustomRateLimiterConfig(RateLimiterConfig):
    DEFAULT_REQUESTS_PER_WINDOW = 200
    API_RATE_LIMITS = {
        'api': {'requests': 100, 'window': 60}
    }

# Usar configuração personalizada
rate_limiter = FlaskRateLimiter(app, config=CustomRateLimiterConfig())
```

## Conclusão

O sistema de rate limiting implementado oferece proteção robusta contra abuso da API, mantendo flexibilidade para diferentes cenários de uso. A configuração adequada e monitoramento regular garantem o equilíbrio entre proteção e usabilidade.

Para dúvidas ou problemas, consulte os logs da aplicação ou entre em contato com a equipe de desenvolvimento.