from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.settings.models import (
    DEFAULT_DIFFUSER_PROMPT,
    DEFAULT_MEMORY_PROMPT,
    DEFAULT_ROLEPLAY_PROMPT,
    DEFAULT_SPARKLE_ASSISTANT_PROMPT,
    DEFAULT_VISION_PERSONA_PROMPT,
)
from infrastructure.database import Base
from shared.config import Config


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_initial_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    permissions: Mapped[list["PermissionORM"]] = relationship(
        "PermissionORM",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class PermissionORM(Base):
    __tablename__ = "user_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission: Mapped[str] = mapped_column(String(128), nullable=False)

    user: Mapped["UserORM"] = relationship("UserORM", back_populates="permissions")


class PersonaORM(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str] = mapped_column(String(32), default="non-binary", nullable=False)
    portrait_path: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    appearance: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class LorebookORM(Base):
    __tablename__ = "lorebooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    entries: Mapped[list["LorebookEntryORM"]] = relationship(
        "LorebookEntryORM",
        back_populates="lorebook",
        cascade="all, delete-orphan",
    )


class LorebookEntryORM(Base):
    __tablename__ = "lorebook_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lorebook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorebooks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    lorebook: Mapped["LorebookORM"] = relationship("LorebookORM", back_populates="entries")


class WorldInfoORM(Base):
    __tablename__ = "worldinfos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    locations: Mapped[list["LocationORM"]] = relationship(
        "LocationORM",
        back_populates="worldinfo",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["EventORM"]] = relationship(
        "EventORM",
        back_populates="worldinfo",
        cascade="all, delete-orphan",
    )


class LocationORM(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worldinfo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worldinfos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    background_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vision_alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    worldinfo: Mapped["WorldInfoORM"] = relationship("WorldInfoORM", back_populates="locations")


class EventORM(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    worldinfo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worldinfos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    one_shot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    worldinfo: Mapped["WorldInfoORM"] = relationship("WorldInfoORM", back_populates="events")


class CharacterORM(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str] = mapped_column(String(32), default="non-binary", nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="private", nullable=False)
    primary_portrait_path: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    dialogue_examples_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    linked_lorebook_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    suggested_worldinfo_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("worldinfos.id", ondelete="SET NULL"), nullable=True
    )
    first_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    initial_location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    initial_relationship: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    preferred_location_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    disliked_location_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    gallery_images: Mapped[list["CharacterImageORM"]] = relationship(
        "CharacterImageORM",
        back_populates="character",
        cascade="all, delete-orphan",
    )
    sprites: Mapped[list["SpriteORM"]] = relationship(
        "SpriteORM",
        back_populates="character",
        cascade="all, delete-orphan",
    )


class CharacterImageORM(Base):
    __tablename__ = "character_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    unlock_threshold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    character: Mapped["CharacterORM"] = relationship("CharacterORM", back_populates="gallery_images")


class SpriteORM(Base):
    __tablename__ = "character_sprites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    emotion: Mapped[str] = mapped_column(String(64), nullable=False)
    variant: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)

    character: Mapped["CharacterORM"] = relationship("CharacterORM", back_populates="sprites")


class ChatSessionORM(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    character_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    persona_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("personas.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    active_worldinfo_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("worldinfos.id", ondelete="SET NULL"), nullable=True
    )
    current_location_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Chat Session", nullable=False)
    relationship_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    events_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cooldown_counter: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    parent_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    persona_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    triggered_event_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    messages: Mapped[list["MessageORM"]] = relationship(
        "MessageORM",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    memories: Mapped[list["MemoryORM"]] = relationship(
        "MemoryORM",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class MessageORM(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    english_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    localized_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    session: Mapped["ChatSessionORM"] = relationship("ChatSessionORM", back_populates="messages")


class MemoryORM(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)

    session: Mapped["ChatSessionORM"] = relationship("ChatSessionORM", back_populates="memories")


class TranslationORM(Base):
    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    english_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_language: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class SettingsORM(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ollama_url: Mapped[str] = mapped_column(String(512), default=Config.DEFAULT_OLLAMA_URL, nullable=False)
    comfyui_url: Mapped[str] = mapped_column(String(512), default=Config.DEFAULT_COMFYUI_URL, nullable=False)
    searxng_url: Mapped[str] = mapped_column(String(512), default=Config.DEFAULT_SEARXNG_URL, nullable=False)
    searxng_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    roleplay_model: Mapped[str] = mapped_column(String(128), default="llama3:8b", nullable=False)
    memory_model: Mapped[str] = mapped_column(String(128), default="llama3:8b", nullable=False)
    assistant_model: Mapped[str] = mapped_column(String(128), default="llama3:8b", nullable=False)
    vision_model: Mapped[str] = mapped_column(String(128), default="llava:latest", nullable=False)

    num_ctx: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    top_p: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    repeat_penalty: Mapped[float] = mapped_column(Float, default=1.1, nullable=False)

    roleplay_prompt: Mapped[str] = mapped_column(Text, default=DEFAULT_ROLEPLAY_PROMPT, nullable=False)
    memory_prompt: Mapped[str] = mapped_column(Text, default=DEFAULT_MEMORY_PROMPT, nullable=False)
    diffuser_prompt: Mapped[str] = mapped_column(Text, default=DEFAULT_DIFFUSER_PROMPT, nullable=False)
    sparkle_assistant_prompt: Mapped[str] = mapped_column(
        Text, default=DEFAULT_SPARKLE_ASSISTANT_PROMPT, nullable=False
    )
    vision_persona_prompt: Mapped[str] = mapped_column(
        Text, default=DEFAULT_VISION_PERSONA_PROMPT, nullable=False
    )
