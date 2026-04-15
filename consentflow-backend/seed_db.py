import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
import asyncpg

DB_URI = os.getenv(
    "DATABASE_URL", 
    "postgresql://consentflow:changeme@localhost:5432/consentflow"
)

USERS_COUNT = 250
CONSENT_TOTAL = 400
AUDIT_TOTAL = 350

PURPOSES = ["analytics", "inference", "model_training", "pii", "webhook"]
DATA_TYPES = ["pii", "telemetry", "model_weights", "predictions", "user_content"]
GATES = ["inference_gate", "dataset_gate", "training_gate", "monitoring_gate"]

async def main():
    print(f"Connecting to {DB_URI}")
    try:
        conn = await asyncpg.connect(DB_URI)
    except Exception as e:
        print(f"Failed to connect to PG: {e}")
        return
        
    print(f"Inserting {USERS_COUNT} users...")
    user_ids = []
    now = datetime.now(timezone.utc)
    
    for i in range(USERS_COUNT):
        user_id = uuid.uuid4()
        user_ids.append(user_id)
        email = f"user_{user_id.hex[:6]}@example.com"
        created_at = now - timedelta(days=random.randint(1, 30), minutes=random.randint(1, 1000))
        await conn.execute("INSERT INTO users (id, email, created_at) VALUES ($1, $2, $3)", user_id, email, created_at)
        
    print(f"Inserting {CONSENT_TOTAL} consent records...")
    for _ in range(CONSENT_TOTAL):
        u_id = random.choice(user_ids)
        purpose = random.choice(PURPOSES)
        d_type = random.choice(DATA_TYPES)
        status = "granted" if random.random() > 0.3 else "revoked"
        updated_at = now - timedelta(days=random.randint(0, 10), hours=random.randint(0, 23))
        
        await conn.execute("""
            INSERT INTO consent_records (user_id, data_type, purpose, status, updated_at) 
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, purpose, data_type) DO UPDATE SET status = EXCLUDED.status, updated_at = EXCLUDED.updated_at
        """, u_id, d_type, purpose, status, updated_at)

    print(f"Inserting {AUDIT_TOTAL} audit log entries...")
    for _ in range(AUDIT_TOTAL):
        event_time = now - timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
        u_id = random.choice(user_ids)
        gate = random.choice(GATES)
        if gate == "inference_gate":
            action = "ALLOWED" if random.random() > 0.05 else "BLOCKED"
        else:
            action = "ALLOWED" if random.random() > 0.2 else "BLOCKED"
            
        c_status = "granted" if action == "ALLOWED" else "revoked"
        purpose = random.choice(PURPOSES)
        trace_id = f"trace-{uuid.uuid4().hex[:8]}"
        meta = '{"redisHit": true}' if random.random() > 0.5 else '{"latencyMs": ' + str(random.randint(2, 10)) + '}'
        
        await conn.execute("""
            INSERT INTO audit_log (event_time, user_id, gate_name, action_taken, consent_status, purpose, metadata, trace_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, event_time, str(u_id), gate, action, c_status, purpose, meta, trace_id)

    print("Seeding complete! 1000 items added.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
