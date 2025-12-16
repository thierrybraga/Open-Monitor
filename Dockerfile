FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependências do sistema necessárias para psycopg2 e weasyprint
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libmagic1 \
    libxml2 \
    libxslt1.1 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do app
COPY . /app

# Expor porta esperada pelo Cloud Run
ENV PORT=4443

# Entry-point com migração + bootstrap
RUN chmod +x /app/entrypoint.sh

# Criar usuário não-root e ajustar permissões para diretórios de escrita
RUN useradd -u 1000 -m appuser && \
    mkdir -p /app/instance /app/logs /app/cache && \
    chown -R appuser:appuser /app

USER appuser

CMD ["/app/entrypoint.sh"]
