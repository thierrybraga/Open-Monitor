from app.app import create_app
from app.extensions.db import db
from app.models.cve_part import CVEPart


def main():
    app = create_app('development')
    with app.app_context():
        count = db.session.query(CVEPart).count()
        print(f"cve_parts rows: {count}")


if __name__ == '__main__':
    main()