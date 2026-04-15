"""
routers/users.py — User management endpoints.

Endpoints
---------
GET    /users              — list all users with consent count + derived status
POST   /users              — create a new user (returns the new UUID)
POST   /users/register     — alias for POST /users (frontend-friendly path)
GET    /users/{user_id}    — look up an existing user by UUID
"""
from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from consentflow.app.models import UserCreateRequest, UserRecord, UserListRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


# ── Dependency helpers ─────────────────────────────────────────────────────────

def _get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


# ── GET /users ─────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[UserListRecord],
    status_code=status.HTTP_200_OK,
    summary="List all users",
    description=(
        "Returns all registered users ordered by most-recently created. "
        "Each record includes the total number of consent records and a "
        "derived status: 'active' (has at least one granted consent), "
        "'revoked' (all consents revoked), or 'pending' (no consents yet)."
    ),
)
async def list_users(
    pool: asyncpg.Pool = Depends(_get_pool),
) -> list[UserListRecord]:
    sql = """
        SELECT
            u.id,
            u.email,
            u.created_at,
            COUNT(c.id)                                          AS consents,
            CASE
                WHEN COUNT(c.id) = 0                             THEN 'pending'
                WHEN COUNT(c.id) FILTER (WHERE c.status = 'granted') > 0 THEN 'active'
                ELSE                                                   'revoked'
            END                                                  AS status
        FROM users u
        LEFT JOIN consent_records c ON c.user_id = u.id
        GROUP BY u.id, u.email, u.created_at
        ORDER BY u.created_at DESC
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
    except asyncpg.PostgresError as exc:
        logger.error("DB error listing users: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    return [
        UserListRecord(
            id=row["id"],
            email=row["email"],
            created_at=row["created_at"],
            consents=row["consents"],
            status=row["status"],
        )
        for row in rows
    ]


# ── Shared create logic ────────────────────────────────────────────────────────

async def _create_user(email: str, pool: asyncpg.Pool) -> UserRecord:
    sql = """
        INSERT INTO users (email)
        VALUES ($1)
        RETURNING id, email, created_at
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(sql, email)
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{email}' already exists.",
        )
    except asyncpg.PostgresError as exc:
        logger.error("DB error creating user: %s", exc)
        raise HTTPException(status_code=500, detail="Database error")

    return UserRecord(
        id=row["id"],
        email=row["email"],
        created_at=row["created_at"],
    )


# ── POST /users ────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=UserRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a new user row with a server-generated UUID. "
        "The UUID returned here is what you pass as `user_id` in "
        "consent requests. Returns 409 if the e-mail is already registered."
    ),
)
async def create_user(
    body: UserCreateRequest,
    pool: asyncpg.Pool = Depends(_get_pool),
) -> UserRecord:
    return await _create_user(body.email, pool)


# ── POST /users/register ──────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (alias)",
    description=(
        "Frontend-friendly alias for POST /users. "
        "Creates a new user and returns their UUID. "
        "Returns 409 if the e-mail is already registered."
    ),
)
async def register_user(
    body: UserCreateRequest,
    pool: asyncpg.Pool = Depends(_get_pool),
) -> UserRecord:
    return await _create_user(body.email, pool)


# ── GET /users/{user_id} ───────────────────────────────────────────────────────

@router.get(
    "/{user_id}",
    response_model=UserListRecord,
    status_code=status.HTTP_200_OK,
    summary="Look up a user by UUID",
    description=(
        "Returns the enriched user record for the given UUID, including "
        "consent count and derived status. Returns 404 if not found."
    ),
)
async def get_user(
    user_id: UUID,
    pool: asyncpg.Pool = Depends(_get_pool),
) -> UserListRecord:
    sql = """
        SELECT
            u.id,
            u.email,
            u.created_at,
            COUNT(c.id)                                          AS consents,
            CASE
                WHEN COUNT(c.id) = 0                             THEN 'pending'
                WHEN COUNT(c.id) FILTER (WHERE c.status = 'granted') > 0 THEN 'active'
                ELSE                                                   'revoked'
            END                                                  AS status
        FROM users u
        LEFT JOIN consent_records c ON c.user_id = u.id
        WHERE u.id = $1
        GROUP BY u.id, u.email, u.created_at
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, user_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )

    return UserListRecord(
        id=row["id"],
        email=row["email"],
        created_at=row["created_at"],
        consents=row["consents"],
        status=row["status"],
    )
