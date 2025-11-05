import os
import sys
import time

# Ensure project root is in sys.path when executed from scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.services.chat_service import ChatService
from app.models import db
from app.models.user import User
from app.models.chat_session import ChatSession


def main():
    # Ensure environment is loaded before app config
    # create_app already handles early .env/.env.example loading via app/app.py changes
    app = create_app()

    with app.app_context():
        print("=== Open-Monitor ChatService Probe ===")
        # Show key environment-related config
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("OPENAI_MODEL") or app.config.get("OPENAI_MODEL")
        org = os.environ.get("OPENAI_ORG_ID") or app.config.get("OPENAI_ORG_ID")
        base_url = os.environ.get("OPENAI_BASE_URL") or app.config.get("OPENAI_BASE_URL")
        print(f"OPENAI_API_KEY present: {bool(openai_api_key)}")
        print(f"OPENAI_MODEL: {model}")
        print(f"OPENAI_ORG_ID: {org}")
        print(f"OPENAI_BASE_URL: {base_url}")

        chat_service = ChatService()
        print(f"ChatService demo_mode: {chat_service.demo_mode}")

        # Prepare a throwaway session for testing generate_response
        try:
            # Ensure a demo user exists
            demo_user = User.query.filter_by(username='demo').first()
            if not demo_user:
                demo_user = User(username='demo', email='demo@example.com', password='demo@teste')
                db.session.add(demo_user)
                db.session.commit()
                print(f"Created demo user id={demo_user.id}")

            import uuid
            session = ChatSession(
                title="Probe Session",
                session_token=str(uuid.uuid4()),
                user_id=demo_user.id,
                is_active=True
            )
            db.session.add(session)
            db.session.commit()
            print(f"Created ChatSession id={session.id}")

            t0 = time.time()
            result = chat_service.process_message("Olá! Teste de integração OpenAI.", session.id, demo_user.id)
            dt = time.time() - t0

            print("=== ChatService Response ===")
            print(f"success: {result.get('success')}")
            print(f"demo_mode: {result.get('demo_mode')}")
            assistant = result.get('assistant_message') or {}
            print(f"assistant_message.content: {assistant.get('content')!r}")
            print(f"processing_time: {result.get('processing_time')} (measured {dt:.3f}s)")
            print(f"assistant_token_count: {assistant.get('token_count')}")
        except Exception as e:
            print("Probe error:", e)


if __name__ == "__main__":
    main()