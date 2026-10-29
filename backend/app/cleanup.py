"""删除会话/角色时清理关联数据与图片文件。"""

from sqlalchemy import delete, select

from .config import AVATARS_DIR, IMAGES_DIR
from .models import (
    Character,
    CharacterFavorite,
    Conversation,
    ConversationVariable,
    GeneratedImage,
    Memory,
    Message,
    WorldEntry,
)


def purge_conversation(db, conversation_id: int) -> None:
    for image in db.scalars(
        select(GeneratedImage).where(GeneratedImage.conversation_id == conversation_id)
    ).all():
        try:
            (IMAGES_DIR / image.filename).unlink(missing_ok=True)
        except OSError:
            pass
        db.delete(image)

    db.execute(
        delete(ConversationVariable).where(
            ConversationVariable.conversation_id == conversation_id
        )
    )
    db.execute(delete(Memory).where(Memory.conversation_id == conversation_id))
    db.execute(delete(Message).where(Message.conversation_id == conversation_id))

    conversation = db.get(Conversation, conversation_id)
    if conversation:
        db.delete(conversation)


def purge_character(db, character: Character) -> None:
    for conversation_id in db.scalars(
        select(Conversation.id).where(Conversation.character_id == character.id)
    ).all():
        purge_conversation(db, conversation_id)

    db.execute(delete(WorldEntry).where(WorldEntry.character_id == character.id))
    db.execute(
        delete(CharacterFavorite).where(
            CharacterFavorite.character_id == character.id
        )
    )

    avatar = (character.avatar_url or "").strip()
    prefix = "/media/avatars/"
    if avatar.startswith(prefix):
        try:
            (AVATARS_DIR / avatar[len(prefix):]).unlink(missing_ok=True)
        except OSError:
            pass

    db.delete(character)
