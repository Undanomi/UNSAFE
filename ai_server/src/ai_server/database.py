from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    target_os: Mapped[str] = mapped_column(Text, nullable=False, default="Debian 13.7.0")
    attack_graph: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    user_flag: Mapped[str | None] = mapped_column(Text)
    system_flag: Mapped[str | None] = mapped_column(Text)
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
    build_repair_attempt_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    machine_access: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    artifact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SkillRecord(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'disabled')", name="skills_status_check"),
        Index("skills_status_idx", "status"),
    )

    skill_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    current_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SkillVersionRecord(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (CheckConstraint("version > 0", name="skill_versions_version_check"),)

    skill_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("skills.skill_id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[list[dict[str, Any]]] = mapped_column(
        "reference_documents", JSONB, nullable=False, default=list
    )
    phases: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    selectors: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    content_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionSkillSnapshotRecord(Base):
    __tablename__ = "session_skill_snapshots"

    session_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("ai_sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    phase: Mapped[str] = mapped_column(String(32), primary_key=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionSkillPlanRecord(Base):
    __tablename__ = "session_skill_plans"

    session_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("ai_sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SessionSkillSnapshotItemRecord(Base):
    __tablename__ = "session_skill_snapshot_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "phase"],
            ["session_skill_snapshots.session_id", "session_skill_snapshots.phase"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["skill_id", "skill_version"],
            ["skill_versions.skill_id", "skill_versions.version"],
        ),
        CheckConstraint("position >= 0", name="skill_snapshot_position_check"),
        UniqueConstraint("session_id", "phase", "position"),
        Index("skill_snapshot_items_version_idx", "skill_id", "skill_version"),
    )

    session_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    phase: Mapped[str] = mapped_column(String(32), primary_key=True)
    skill_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    skill_version: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    selected_reference_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    selection_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    content_checksum: Mapped[str] = mapped_column(CHAR(64), nullable=False)


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
