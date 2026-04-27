import asyncio
from pathlib import Path

from sqlalchemy import select

from src.auth.passwords import hash_password
from src.config import get_settings
from src.db.engine import async_session_factory
from src.db.models import Document, User
from src.rag.embeddings import load_embedding_model
from src.services.documents import create_document, ingest_document

SAMPLE_DOCUMENTS = [
    {
        "title": "Getting Started",
        "source_url": "https://docs.support-rag.local/getting-started",
        "content": (
            "Welcome to our platform! Here are some common questions:\n\n"
            "Q: How do I create an account?\n"
            "A: Click the 'Sign Up' button on the homepage and fill in your details. "
            "You'll receive a confirmation email within minutes.\n\n"
            "Q: What are the system requirements?\n"
            "A: Our platform works in any modern web browser (Chrome, Firefox, Safari, Edge). "
            "No installation required.\n\n"
            "Q: How do I navigate the dashboard?\n"
            "A: After logging in, you'll see the main dashboard with navigation on the left sidebar. "
            "Key sections include Chat, Documents, and Settings.\n\n"
            "Q: Is there a mobile app?\n"
            "A: Our platform is fully responsive and works great on mobile browsers. "
            "A dedicated mobile app is planned for the future."
        ),
        "category": "FAQ",
    },
    {
        "title": "Account Management",
        "source_url": "https://docs.support-rag.local/account-management",
        "content": (
            "Frequently asked questions about managing your account:\n\n"
            "Q: How do I reset my password?\n"
            "A: Go to the login page and click 'Forgot Password'. Enter your email address "
            "and you'll receive a password reset link within 5 minutes.\n\n"
            "Q: How do I change my profile settings?\n"
            "A: Navigate to Settings > Profile from the sidebar. You can update your display name, "
            "email address, and avatar from this page.\n\n"
            "Q: How do I enable two-factor authentication?\n"
            "A: Go to Settings > Security > Two-Factor Authentication. You can use an authenticator "
            "app like Google Authenticator or Authy.\n\n"
            "Q: Can I change my username?\n"
            "A: Usernames cannot be changed after registration for security reasons. "
            "Contact support if you need to update your username.\n\n"
            "Q: How do I delete my account?\n"
            "A: Go to Settings > Account > Delete Account. This action is permanent and "
            "cannot be undone. All your data will be removed within 30 days."
        ),
        "category": "FAQ",
    },
    {
        "title": "API Integration",
        "source_url": "https://docs.support-rag.local/api-integration",
        "content": (
            "API Integration Guide:\n\n"
            "Q: What is API Integration?\n"
            "A: API Integration allows you to connect your applications with our platform. "
            "You can authenticate requests, manage keys, and configure webhooks.\n\n"
            "Q: How do I get an API key for API Integration?\n"
            "A: Navigate to Settings > API Keys and click 'Generate New Key'. "
            "You can create keys with different permission scopes for your API Integration.\n\n"
            "Q: What are the rate limits for API Integration?\n"
            "A: Free tier: 100 requests per minute, 10,000 per day. "
            "Pro tier: 1,000 requests per minute, 100,000 per day. "
            "Enterprise tier: custom limits available.\n\n"
            "Q: How do I authenticate API Integration requests?\n"
            "A: Include your API key in the Authorization header: "
            "Authorization: Bearer YOUR_API_KEY. You can also use query parameter ?api_key=YOUR_KEY.\n\n"
            "Q: Do you support webhooks for API Integration?\n"
            "A: Yes! Configure webhooks in Settings > Integrations > Webhooks. "
            "We support HTTPS endpoints and deliver events for document changes, "
            "user actions, and system events.\n\n"
            "Q: Where can I find the API Integration documentation?\n"
            "A: Full API Integration documentation is available at /docs (Swagger UI) and /redoc (ReDoc). "
            "Interactive examples are provided for all endpoints."
        ),
        "category": "FAQ",
    },
    {
        "title": "Project Information",
        "source_url": "https://github.com/volsSha/Qa-bot",
        "content": (
            "Information about our project and how to find us:\n\n"
            "Q: What is this project?\n"
            "A: This is an AI-powered support assistant (RAG system) that helps users find answers "
            "from your knowledge base. It uses retrieval-augmented generation to provide accurate "
            "responses based on your documentation.\n\n"
            "Q: What is your website?\n"
            "A: Our project repository is available on GitHub at github.com/volsSha/Qa-bot. "
            "You can find the source code, documentation, and contribution guidelines there.\n\n"
            "Q: How can I find your site?\n"
            "A: Visit github.com/volsSha/Qa-bot to access our project. The repository contains "
            "the full source code, setup instructions, and usage examples.\n\n"
            "Q: Is the project open source?\n"
            "A: Yes, the project is open source and available on GitHub. "
            "You can report issues, submit pull requests, and contribute to the development.\n\n"
            "Q: How can I contact the team?\n"
            "A: You can reach us through GitHub issues on our repository page, "
            "or by email at the contact information provided in the repository README."
        ),
        "category": "About",
    },
]


async def seed():
    settings = get_settings()

    Path("data").mkdir(exist_ok=True)

    print("Loading embedding model...")
    load_embedding_model()

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.seed.admin_username)
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            admin = User(
                username=settings.seed.admin_username,
                email=settings.seed.admin_email,
                hashed_password=hash_password(settings.seed.admin_password),
                is_admin=True,
            )
            session.add(admin)
            await session.commit()
            print(f"Created admin user: {settings.seed.admin_username}")
        else:
            print(f"Admin user '{settings.seed.admin_username}' already exists, skipping")

        result = await session.execute(select(Document))
        existing_count = len(result.scalars().all())

        if existing_count == 0:
            total_chunks = 0
            for doc_data in SAMPLE_DOCUMENTS:
                doc = await create_document(
                    session,
                    title=doc_data["title"],
                    content=doc_data["content"],
                    source_url=doc_data.get("source_url"),
                    category=doc_data["category"],
                )
                await session.commit()
                await session.refresh(doc)

                chunk_count = await ingest_document(
                    session, doc.id,
                )
                total_chunks += chunk_count
                print(f"  Created document: {doc_data['title']} ({chunk_count} chunks)")

            print(
                f"\nSeeding complete: 1 admin user, "
                f"{len(SAMPLE_DOCUMENTS)} documents, {total_chunks} total chunks"
            )
        else:
            print(f"{existing_count} document(s) already exist, skipping document seeding")

if __name__ == "__main__":
    asyncio.run(seed())
