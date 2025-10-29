import io
import sys
from pathlib import Path

# Garantir que o diretório raiz esteja no sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.app import create_app


def main():
    app = create_app('development')
    app.testing = True
    with app.app_context():
        client = app.test_client()
        resp = client.get('/reports/')
        print('Status:', resp.status_code)
        content = resp.data.decode('utf-8', errors='ignore')
        print('Contains title:', 'Relatórios de Segurança' in content)
        # Print a snippet to help debugging
        print('Snippet:', content[:500].replace('\n', ' ')[:500])


if __name__ == '__main__':
    main()