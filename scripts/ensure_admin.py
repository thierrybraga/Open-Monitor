"""
Ensure the admin user exists and has the specified password.

Usage: python scripts/ensure_admin.py [optional_password]
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for 'app' package imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models.user import User


def ensure_admin(password: str = 'admin@teste') -> None:
    app = create_app('development')
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        if user is None:
            user = User(username='admin', email='admin@example.com')
            user.is_admin = True
            user.is_active = True
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print(f'ADMIN_CREATED id={user.id}')
        else:
            user.set_password(password)
            db.session.commit()
            print(f'ADMIN_UPDATED id={user.id}')

        print('PASSWORD_VALID', user.check_password(password))


if __name__ == '__main__':
    pwd = 'admin@teste'
    if len(sys.argv) > 1 and sys.argv[1]:
        pwd = sys.argv[1]
    ensure_admin(pwd)