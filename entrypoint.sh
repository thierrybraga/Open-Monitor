#!/bin/sh
set -e

export FLASK_APP="app.app:create_app"
export FLASK_ENV="production"

python -m compileall -q app || true
flask db upgrade || true

python - <<'PY'
from app.app import create_app
from app.main_startup import initialize_database
app = create_app('production')
initialize_database(app)
PY

exec gunicorn --bind 0.0.0.0:${PORT:-4443} \
  --workers ${WEB_CONCURRENCY:-3} \
  --threads ${GUNICORN_THREADS:-4} \
  --access-logfile - --error-logfile - \
  wsgi:application
