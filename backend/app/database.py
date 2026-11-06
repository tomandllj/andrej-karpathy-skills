from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 管理员在库里的固定身份。ini 里的账号密码只是登录凭据，改 ini 不再换身份；
# 下划线让公开注册的正则（只认字母数字）天然注册不了这个名字
ADMIN_DB_USERNAME = "__admin__"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_comment_context_columns() -> None:
    """给旧库的 comment 表补前后文字段（已存在则跳过）。"""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(comment)").fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if "context_prefix" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE comment ADD COLUMN context_prefix TEXT"
            )
        if "context_suffix" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE comment ADD COLUMN context_suffix TEXT"
            )


def _migrate_document_owner_columns() -> None:
    """给旧库的 document 表补所属用户和文件夹（已存在则跳过）。"""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(document)").fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if "user_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE document ADD COLUMN user_id INTEGER")
        if "folder_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE document ADD COLUMN folder_id INTEGER")


def _migrate_folder_pin_column() -> None:
    """给旧库的 folder 表补置顶时间（已存在则跳过）。"""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(folder)").fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if "pinned_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE folder ADD COLUMN pinned_at TEXT")


def _migrate_app_user_password_column() -> None:
    """给旧库的 app_user 表补密码哈希列（已存在则跳过）；管理员该列恒为空。"""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(app_user)").fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}
        if "password_hash" not in cols:
            conn.exec_driver_sql("ALTER TABLE app_user ADD COLUMN password_hash TEXT")


def _migrate_admin_identity() -> None:
    """把历史管理员行并入固定身份 __admin__，文件夹、文档、收件记录跟着转移。

    旧版按 ini 用户名建管理员行；ini 一改就另建新行，旧行名下的数据全成了孤儿。
    管理员行从不存密码哈希（普通用户注册必写哈希），据此识别全部旧管理员行。
    """
    with engine.begin() as conn:
        fixed = conn.execute(
            text("SELECT id FROM app_user WHERE username = :n"),
            {"n": ADMIN_DB_USERNAME},
        ).fetchone()
        olds = conn.execute(
            text(
                "SELECT id FROM app_user "
                "WHERE password_hash IS NULL AND username != :n ORDER BY id"
            ),
            {"n": ADMIN_DB_USERNAME},
        ).fetchall()
        if not olds:
            return
        if fixed is None:
            # 最早的管理员行直接改名，保留原 id，名下数据和会话都不动
            first_id = olds[0][0]
            conn.execute(
                text("UPDATE app_user SET username = :n WHERE id = :i"),
                {"n": ADMIN_DB_USERNAME, "i": first_id},
            )
            fixed_id = first_id
            olds = olds[1:]
        else:
            fixed_id = fixed[0]
        # 其余旧管理员行：数据并入固定行后删除
        for (old_id,) in olds:
            conn.execute(
                text("UPDATE folder SET user_id = :f WHERE user_id = :o"),
                {"f": fixed_id, "o": old_id},
            )
            conn.execute(
                text("UPDATE document SET user_id = :f WHERE user_id = :o"),
                {"f": fixed_id, "o": old_id},
            )
            conn.execute(
                text("UPDATE user_doc SET user_id = :f WHERE user_id = :o"),
                {"f": fixed_id, "o": old_id},
            )
            conn.execute(
                text("DELETE FROM app_user WHERE id = :o"),
                {"o": old_id},
            )


def _repair_doc_updated_at_touched_by_comments() -> None:
    """纠正旧逻辑：批注改动曾误写 document.updated_at，导致「作者提交」跟评论时间绑在一起。

    仅当文档 updated_at 恰好等于某条未删除批注的 updated_at 时，回退到最新正文版本时间。
    """
    with engine.begin() as conn:
        docs = conn.exec_driver_sql("PRAGMA table_info(document)").fetchall()
        vers = conn.exec_driver_sql("PRAGMA table_info(document_version)").fetchall()
        comments = conn.exec_driver_sql("PRAGMA table_info(comment)").fetchall()
        if not docs or not vers or not comments:
            return
        conn.exec_driver_sql(
            """
            UPDATE document
            SET updated_at = (
                SELECT MAX(v.created_at)
                FROM document_version v
                WHERE v.doc_id = document.id
            )
            WHERE EXISTS (
                SELECT 1 FROM comment c
                WHERE c.doc_id = document.id
                  AND c.is_deleted = 0
                  AND c.updated_at = document.updated_at
            )
            AND EXISTS (
                SELECT 1 FROM document_version v2
                WHERE v2.doc_id = document.id
            )
            """
        )


def init_db():
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_comment_context_columns()
    _migrate_document_owner_columns()
    _migrate_folder_pin_column()
    _migrate_app_user_password_column()
    _migrate_admin_identity()
    _repair_doc_updated_at_touched_by_comments()
