"""
Database seed script for Hermass StrategyQuant Replica.

Usage:
    cd /Users/lv111101/Documents/kimi/workspace/hermass-strategyquant-replica/backend
    python3 scripts/seed_db.py

Creates a demo user with sample strategies for quick testing.
"""
import asyncio
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models import Base, User, Strategy, StrategyStatus
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await _seed_user(session)
        await _seed_strategies(session)
        await session.commit()
        print("✅ Database seeded successfully")


async def _seed_user(session: AsyncSession) -> None:
    result = await session.execute(select(User).where(User.email == "demo@hermass.com"))
    if result.scalar_one_or_none():
        print("  Demo user already exists, skipping")
        return

    user = User(
        email="demo@hermass.com",
        hashed_password=get_password_hash("demo1234"),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    print(f"  Created demo user: {user.id}")


async def _seed_strategies(session: AsyncSession) -> None:
    result = await session.execute(select(User).where(User.email == "demo@hermass.com"))
    user = result.scalar_one_or_none()
    if not user:
        print("  No demo user found, skipping strategies")
        return

    existing = await session.execute(
        select(Strategy).where(Strategy.user_id == user.id)
    )
    if existing.scalars().first():
        print("  Demo strategies already exist, skipping")
        return

    strategies = [
        Strategy(
            user_id=user.id,
            name="MA 金叉策略",
            description="SMA 20 上穿 SMA 50 时买入，下穿时卖出",
            ir_json={
                "version": "1.0",
                "strategy_id": "demo-ma-cross",
                "name": "MA Cross Strategy",
                "description": "Simple SMA 20 > 50 crossover",
                "timeframe": "1d",
                "market": "CN",
                "nodes": [],
                "edges": [],
            },
            config={"symbol": "000001.SZ", "timeframe": "1d", "initial_capital": 1_000_000},
            status=StrategyStatus.ACTIVE,
        ),
        Strategy(
            user_id=user.id,
            name="RSI 超卖反弹",
            description="RSI < 30 买入，RSI > 70 卖出",
            ir_json={
                "version": "1.0",
                "strategy_id": "demo-rsi-oversold",
                "name": "RSI Oversold Reversal",
                "description": "RSI oversold bounce strategy",
                "timeframe": "1d",
                "market": "CN",
                "nodes": [],
                "edges": [],
            },
            config={"symbol": "000002.SZ", "timeframe": "1d", "initial_capital": 1_000_000},
            status=StrategyStatus.DRAFT,
        ),
    ]

    for s in strategies:
        session.add(s)

    print(f"  Created {len(strategies)} demo strategies")


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")


def _sync_database_url() -> str:
    from app.core.config import get_settings

    database_url = get_settings().DATABASE_URL
    return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def _create_sync_session() -> Session:
    sync_engine = create_engine(_sync_database_url(), pool_pre_ping=True, future=True)
    return Session(sync_engine, autoflush=False, expire_on_commit=False)


def create_tables_sync() -> None:
    sync_engine = create_engine(_sync_database_url(), pool_pre_ping=True, future=True)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    print("✅ Tables created (sync fallback)")


def seed_sync() -> None:
    with _create_sync_session() as session:
        _seed_user_sync(session)
        _seed_strategies_sync(session)
        session.commit()
    print("✅ Database seeded successfully (sync fallback)")


def _seed_user_sync(session: Session) -> None:
    user = session.execute(select(User).where(User.email == "demo@hermass.com")).scalar_one_or_none()
    if user:
        print("  Demo user already exists, skipping")
        return

    user = User(
        email="demo@hermass.com",
        hashed_password=get_password_hash("demo1234"),
        is_active=True,
    )
    session.add(user)
    session.flush()
    print(f"  Created demo user: {user.id}")


def _seed_strategies_sync(session: Session) -> None:
    user = session.execute(select(User).where(User.email == "demo@hermass.com")).scalar_one_or_none()
    if not user:
        print("  No demo user found, skipping strategies")
        return

    existing = session.execute(select(Strategy).where(Strategy.user_id == user.id))
    if existing.scalars().first():
        print("  Demo strategies already exist, skipping")
        return

    strategies = [
        Strategy(
            user_id=user.id,
            name="MA 金叉策略",
            description="SMA 20 上穿 SMA 50 时买入，下穿时卖出",
            ir_json={
                "version": "1.0",
                "strategy_id": "demo-ma-cross",
                "name": "MA Cross Strategy",
                "description": "Simple SMA 20 > 50 crossover",
                "timeframe": "1d",
                "market": "CN",
                "nodes": [],
                "edges": [],
            },
            config={"symbol": "000001.SZ", "timeframe": "1d", "initial_capital": 1_000_000},
            status=StrategyStatus.ACTIVE,
        ),
        Strategy(
            user_id=user.id,
            name="RSI 超卖反弹",
            description="RSI < 30 买入，RSI > 70 卖出",
            ir_json={
                "version": "1.0",
                "strategy_id": "demo-rsi-oversold",
                "name": "RSI Oversold Reversal",
                "description": "RSI oversold bounce strategy",
                "timeframe": "1d",
                "market": "CN",
                "nodes": [],
                "edges": [],
            },
            config={"symbol": "000002.SZ", "timeframe": "1d", "initial_capital": 1_000_000},
            status=StrategyStatus.DRAFT,
        ),
    ]

    for strategy in strategies:
        session.add(strategy)

    print(f"  Created {len(strategies)} demo strategies")


def should_fallback_to_sync(exc: Exception) -> bool:
    text = f"{type(exc).__module__}.{type(exc).__name__}: {exc}".lower()
    asyncpg_markers = ("asyncpg", "event loop", "future attached", "another loop")
    return any(marker in text for marker in asyncpg_markers)


def run_async_seed(create_tables_first: bool) -> None:
    if create_tables_first:
        asyncio.run(create_tables())
    asyncio.run(seed())


def run_sync_seed(create_tables_first: bool) -> None:
    if create_tables_first:
        create_tables_sync()
    seed_sync()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed Hermass database")
    parser.add_argument("--create-tables", action="store_true", help="Create tables before seeding")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Use psycopg2 sync fallback directly, useful for Python 3.14 + asyncpg local setup issues",
    )
    args = parser.parse_args()

    if args.sync:
        run_sync_seed(args.create_tables)
    else:
        try:
            run_async_seed(args.create_tables)
        except Exception as exc:
            if not should_fallback_to_sync(exc):
                raise
            print(f"⚠️ Async seed failed ({type(exc).__name__}: {exc}); retrying with psycopg2 sync fallback")
            run_sync_seed(args.create_tables)
