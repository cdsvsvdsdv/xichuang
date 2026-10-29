from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def ensure_schema() -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(conversations)").fetchall()
        columns = {row[1] for row in rows}
        if "summary_upto_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE conversations ADD COLUMN summary_upto_id INTEGER NOT NULL DEFAULT 0"
            )

        character_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(characters)").fetchall()
        }
        if "avatar_url" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN avatar_url TEXT NOT NULL DEFAULT ''"
            )
        if "tags" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'"
            )
        if "favorite" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0"
            )
        if "alternates" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN alternates TEXT NOT NULL DEFAULT '[]'"
            )
        if "system_prompt" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN system_prompt TEXT NOT NULL DEFAULT ''"
            )
        if "created_by" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN created_by INTEGER"
            )
        if "html_greeting" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN html_greeting TEXT NOT NULL DEFAULT ''"
            )
        if "card_rules" not in character_columns:
            conn.exec_driver_sql(
                "ALTER TABLE characters ADD COLUMN card_rules TEXT NOT NULL DEFAULT ''"
            )

        if "memory_updated_at" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE conversations ADD COLUMN memory_updated_at DATETIME"
            )

        world_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(world_entries)").fetchall()
        }
        if world_columns:
            if "keywords_secondary" not in world_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE world_entries ADD COLUMN keywords_secondary TEXT NOT NULL DEFAULT '[]'"
                )
            if "logic" not in world_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE world_entries ADD COLUMN logic TEXT NOT NULL DEFAULT 'and_any'"
                )
            if "depth" not in world_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE world_entries ADD COLUMN depth INTEGER"
                )
            if "sticky" not in world_columns:
                conn.exec_driver_sql(
                    "ALTER TABLE world_entries ADD COLUMN sticky INTEGER NOT NULL DEFAULT 0"
                )

        if "user_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE conversations ADD COLUMN user_id INTEGER"
            )

        profile_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(profile)").fetchall()
        }
        if profile_columns and "user_id" not in profile_columns:
            conn.exec_driver_sql("ALTER TABLE profile ADD COLUMN user_id INTEGER")

        message_columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(messages)").fetchall()
        }
        if "variants" not in message_columns:
            conn.exec_driver_sql(
                "ALTER TABLE messages ADD COLUMN variants TEXT NOT NULL DEFAULT '[]'"
            )
        if "active_variant" not in message_columns:
            conn.exec_driver_sql(
                "ALTER TABLE messages ADD COLUMN active_variant INTEGER NOT NULL DEFAULT 0"
            )
