from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ScenarioRecord(Base):
    __tablename__ = "scenarios"

    scenario_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScenarioVersionRecord(Base):
    __tablename__ = "scenario_versions"

    scenario_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("scenarios.scenario_id"), primary_key=True
    )
    scenario_version_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_definition: Mapped[str] = mapped_column(Text, nullable=False)
    target_os: Mapped[str] = mapped_column(Text, nullable=False, default="Ubuntu 26.04")
    attack_graph: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_code_path: Mapped[str | None] = mapped_column(Text)
    generated_code_checksum: Mapped[str | None] = mapped_column(CHAR(64))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AISessionRecord(Base):
    __tablename__ = "ai_sessions"
    __table_args__ = (Index("ai_sessions_owner_updated_idx", "owner_user_id", "updated_at"),)

    session_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    machine_information: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scenario_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("scenarios.scenario_id")
    )
    scenario_version_id: Mapped[str | None] = mapped_column(String(128))
    generated_code_path: Mapped[str | None] = mapped_column(Text)
    generated_code_checksum: Mapped[str | None] = mapped_column(CHAR(64))
    build_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
    build_status: Mapped[str | None] = mapped_column(Text)
    build_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    build_repair_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    machine_access: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    artifact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def sqlalchemy_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+asyncpg")
    if url.drivername == "postgresql+asyncpg":
        return url
    raise ValueError("DATABASE_URL must use PostgreSQL with the asyncpg driver")


def create_database_engine(database_url: str, min_size: int, max_size: int) -> AsyncEngine:
    if min_size > max_size:
        raise ValueError("DATABASE_POOL_MIN_SIZE must not exceed DATABASE_POOL_MAX_SIZE")
    return create_async_engine(
        sqlalchemy_database_url(database_url),
        pool_size=min_size,
        max_overflow=max_size - min_size,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
