from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CharacterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tagline: str
    greeting: str
    default_model: str


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    character_id: int
    title: str
    model: str
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime
    variants: list[str] = []
    active_variant: int = 0


class ConversationCreate(BaseModel):
    character_id: int
    model: str | None = None
    greeting_index: int | None = None


class ChatIn(BaseModel):
    conversation_id: int
    content: str
    model: str | None = None


class RegenerateIn(BaseModel):
    conversation_id: int
    model: str | None = None


class MessageUpdate(BaseModel):
    content: str


class SwipeIn(BaseModel):
    index: int


class RegisterIn(BaseModel):
    username: str
    password: str
    invite: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class VariableIn(BaseModel):
    key: str
    value: str = ""


class VariableUpdate(BaseModel):
    key: str | None = None
    value: str | None = None


class WorldEntryIn(BaseModel):
    keywords: list[str] = []
    keywords_secondary: list[str] = []
    logic: str = "and_any"
    depth: int | None = None
    sticky: int = 0
    content: str
    constant: bool = False
    enabled: bool = True


class WorldEntryUpdate(BaseModel):
    keywords: list[str] | None = None
    keywords_secondary: list[str] | None = None
    logic: str | None = None
    depth: int | None = None
    sticky: int | None = None
    content: str | None = None
    constant: bool | None = None
    enabled: bool | None = None


class CharacterUpdate(BaseModel):
    avatar_url: str | None = None
    tagline: str | None = None
    tags: list[str] | None = None
    system_prompt: str | None = None


class FavoriteIn(BaseModel):
    favorite: bool


class MemoryUpdate(BaseModel):
    content: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    persona: str | None = None
    theme: str | None = None
    background_url: str | None = None


class ImageGenerateIn(BaseModel):
    conversation_id: int
    prompt: str | None = None
    size: str | None = None
