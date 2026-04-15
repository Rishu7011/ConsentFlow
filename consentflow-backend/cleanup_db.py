import asyncio
import os
import asyncpg

DB_URI = os.getenv(
    "DATABASE_URL", 
    "postgresql://consentflow:changeme@localhost:5432/consentflow"
)

async def main():
    try:
        print("Trying password 'changeme'...")
        conn = await asyncpg.connect("postgresql://consentflow:changeme@localhost:5432/consentflow")
    except asyncpg.exceptions.InvalidPasswordError:
        print("Trying password 'consentflow'...")
        try:
            conn = await asyncpg.connect("postgresql://consentflow:consentflow@localhost:5432/consentflow")
        except Exception as e:
            print(f"Failed to connect to PG: {e}")
            return
    except Exception as e:
        print(f"Failed to connect to PG: {e}")
        return
        
    print("Clearing tables...")
    
    # 1. Delete dependent tables
    await conn.execute("DELETE FROM chat_log;")
    await conn.execute("DELETE FROM audit_log;")
    await conn.execute("DELETE FROM consent_records;")
    await conn.execute("DELETE FROM chat_memory;")
    await conn.execute("DELETE FROM consent_freeze_log;")
    # policy_scans doesn't necessarily depend on users, but we can clear it if needed.
    await conn.execute("DELETE FROM policy_scans;")
    
    # 2. Delete all users except demo user
    await conn.execute("DELETE FROM users WHERE email != 'demo@consentflow.dev';")
    
    # 3. Ensure the demo user exists (in case it was somehow deleted)
    await conn.execute("""
        INSERT INTO users (id, email)
        VALUES ('550e8400-e29b-41d4-a716-446655440000', 'demo@consentflow.dev')
        ON CONFLICT (id) DO NOTHING;
    """)

    print("Cleanup complete! All chats and additional users cleared.")
    print("Only demo@consentflow.dev (550e8400-e29b-41d4-a716-446655440000) remains.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
