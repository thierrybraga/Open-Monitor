# Utility script to update the admin user's password safely

from app import create_app
from app.extensions import db
from app.models.user import User


def main():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        if not user:
            print('ERROR: Admin user not found')
            return
        print(f"Found admin: id={user.id} username={user.username} email={user.email}")
        try:
            user.set_password('admin@teste')
            db.session.commit()
            print('Password updated to admin@teste')
            print('Check new password ->', user.check_password('admin@teste'))
        except Exception as e:
            db.session.rollback()
            print('ERROR updating password:', e)
            raise


if __name__ == '__main__':
    main()