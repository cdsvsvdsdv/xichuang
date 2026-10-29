from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    tagline: Mapped[str] = mapped_column(String(120), default="")
    persona: Mapped[str] = mapped_column(Text)
    greeting: Mapped[str] = mapped_column(Text)
    default_model: Mapped[str] = mapped_column(String(50), default="deepseek-chat")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    tags: Mapped[str] = mapped_column(Text, default="[]")
    alternates: Mapped[str] = mapped_column(Text, default="[]")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(120), default="新对话")
    model: Mapped[str] = mapped_column(String(50), default="deepseek-chat")
    summary: Mapped[str] = mapped_column(Text, default="")
    summary_upto_id: Mapped[int] = mapped_column(Integer, default=0)
    memory_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    character = relationship("Character")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(50), default="")
    variants: Mapped[str] = mapped_column(Text, default="[]")
    active_variant: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    prompt: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(30), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80), default="")
    persona: Mapped[str] = mapped_column(Text, default="")
    theme: Mapped[str] = mapped_column(String(30), default="default")
    background_url: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ConversationVariable(Base):
    __tablename__ = "conversation_variables"
    __table_args__ = (
        UniqueConstraint("conversation_id", "key", name="uq_conversation_var"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    key: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class WorldEntry(Base):
    __tablename__ = "world_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True, index=True
    )
    keywords: Mapped[str] = mapped_column(Text, default="[]")
    keywords_secondary: Mapped[str] = mapped_column(Text, default="[]")
    logic: Mapped[str] = mapped_column(String(20), default="and_any")
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sticky: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    constant: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="fact")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
