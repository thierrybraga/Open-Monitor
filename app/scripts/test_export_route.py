import os
import sys


def main(report_id: int = 2, fmt: str = 'pdf'):
    # Garantir que o pacote 'app' seja importável
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(app_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from app.app import create_app

    app = create_app()
    with app.app_context():
        client = app.test_client()
        path = f"/reports/{report_id}/export/{fmt}"
        resp = client.get(path)
        print({
            'path': path,
            'status_code': resp.status_code,
            'content_type': resp.headers.get('Content-Type'),
            'content_length': resp.headers.get('Content-Length'),
            'disposition': resp.headers.get('Content-Disposition'),
        })

        # Salvar arquivo retornado para validação, se ok
        if resp.status_code == 200:
            out_dir = 'temp'
            os.makedirs(out_dir, exist_ok=True)
            filename = f"route_export_{report_id}.{fmt}"
            out_path = os.path.join(out_dir, filename)
            with open(out_path, 'wb') as f:
                f.write(resp.data)
            print({'saved_file': out_path})


if __name__ == '__main__':
    # Permitir passar o ID via argumento
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    main(report_id=rid)