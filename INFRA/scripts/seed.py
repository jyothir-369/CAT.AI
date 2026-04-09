"""
Dev seed script — creates demo workspace, test users, and sample data.

Usage:
    cd apps/api
    python ../../scripts/seed.py
"""
import asyncio
import os
import sys

# Ensure api/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))


async def seed():
    from db.session import engine, Base, AsyncSessionLocal
    import db.models.user           # noqa: F401
    import db.models.conversation   # noqa: F401
    import db.models.knowledge      # noqa: F401
    import db.models.memory         # noqa: F401
    import db.models.workflow       # noqa: F401
    import db.models.billing        # noqa: F401
    import db.models.audit          # noqa: F401
    import db.models.integrations   # noqa: F401

    from db.models.user import User, Organization, Membership, RoleEnum, PlanEnum
    from db.models.conversation import Conversation, Message, MessageRoleEnum
    from db.models.knowledge import KnowledgeBase
    from db.models.billing import Subscription
    from core.security import hash_password
    from sqlalchemy import select

    print("🌱  Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # ── Check if already seeded ───────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "admin@catai.dev"))
        if result.scalar_one_or_none():
            print("✅  Already seeded — skipping")
            return

        # ── Admin user ────────────────────────────────────────────────────────
        admin = User(
            email="admin@catai.dev",
            name="Admin User",
            hashed_password=hash_password("password123"),
            is_active=True,
            is_superadmin=True,
        )
        db.add(admin)
        await db.flush()

        # ── Demo user ─────────────────────────────────────────────────────────
        demo = User(
            email="demo@catai.dev",
            name="Demo User",
            hashed_password=hash_password("password123"),
            is_active=True,
        )
        db.add(demo)
        await db.flush()

        # ── Demo workspace ────────────────────────────────────────────────────
        org = Organization(
            name="CAT AI Demo",
            slug="catai-demo",
            owner_id=demo.id,
            plan=PlanEnum.pro,
            system_prompt=(
                "You are a helpful AI assistant for the CAT AI demo workspace. "
                "Be concise, accurate, and friendly."
            ),
            default_model="gpt-4o",
        )
        db.add(org)
        await db.flush()

        # Memberships
        db.add(Membership(user_id=demo.id, org_id=org.id, role=RoleEnum.owner))
        db.add(Membership(user_id=admin.id, org_id=org.id, role=RoleEnum.admin))

        # Pro subscription
        db.add(Subscription(org_id=org.id, plan=PlanEnum.pro, status="active"))

        # ── Sample conversation ───────────────────────────────────────────────
        conv = Conversation(
            org_id=org.id,
            user_id=demo.id,
            title="Welcome to CAT AI",
            model_id="gpt-4o",
        )
        db.add(conv)
        await db.flush()

        db.add(Message(
            conversation_id=conv.id,
            role=MessageRoleEnum.user,
            content="What can CAT AI do?",
        ))
        db.add(Message(
            conversation_id=conv.id,
            role=MessageRoleEnum.assistant,
            content=(
                "CAT AI is a unified AI workspace that combines:\n\n"
                "• **Multi-model chat** — GPT-4o, Claude, Groq, and more\n"
                "• **Knowledge bases** — upload documents for RAG-powered Q&A\n"
                "• **Workflow automation** — build AI workflows with webhook/cron triggers\n"
                "• **Team workspaces** — RBAC, shared knowledge, usage tracking\n\n"
                "How can I help you get started?"
            ),
            model_id="gpt-4o",
            tokens_in=20,
            tokens_out=80,
        ))

        # ── Sample knowledge base ─────────────────────────────────────────────
        kb = KnowledgeBase(
            org_id=org.id,
            name="Product Documentation",
            description="Official CAT AI product docs and guides",
            embedding_model="text-embedding-3-small",
            chunk_strategy="fixed",
            doc_count=0,
        )
        db.add(kb)

        await db.commit()

        print("✅  Seed complete!")
        print(f"    Admin:  admin@catai.dev / password123")
        print(f"    Demo:   demo@catai.dev  / password123")
        print(f"    Org ID: {org.id}")
        print(f"    Conv:   {conv.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())