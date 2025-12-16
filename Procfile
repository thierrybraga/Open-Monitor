# Process types for platforms like Heroku/Render/Fly.io
#
# web: Servidor WSGI em produção usando gunicorn
# - Usa a aplicação WSGI exposta em `wsgi:application`
# - Respeita variáveis de ambiente: `PORT`, `WEB_CONCURRENCY`, `GUNICORN_THREADS`
# - Principais endpoints da aplicação: `/` (health/readiness), `/api/*` (APIs)
# - Variáveis de ambiente suportadas pelo app (exemplos):
#   SECRET_KEY, DATABASE_URL, BASE_URL, FLASK_ENV, PUBLIC_MODE,
#   LOGIN_ENABLED_IN_PUBLIC_MODE, LOG_LEVEL, ANALYTICS_CACHE_TTL, NVD_API_KEY

web: gunicorn --bind 0.0.0.0:${PORT:-4443} --workers ${WEB_CONCURRENCY:-3} --threads ${GUNICORN_THREADS:-4} --access-logfile - --error-logfile - wsgi:application
