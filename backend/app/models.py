from sqlalchemy import CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppUser(Base):
    """登录账号。email 预留给以后的修改、回复通知；password_hash 只有普通用户有。"""

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserDoc(Base):
    """谁收到了哪篇文档、归在自己的哪个文件夹；只影响自己的列表，不动原文。"""

    __tablename__ = "user_doc"
    __table_args__ = (UniqueConstraint("user_id", "doc_id", name="uq_user_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    folder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 最近一次打开分享链接时的权限，作为收件人之后的默认权限
    permission: Mapped[str] = mapped_column(String(16), nullable=False, default="read")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class Folder(Base):
    """某个账号自己的文件夹。"""

    __tablename__ = "folder"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    pinned_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_secret: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="无标题文档")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    folder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DocumentShare(Base):
    __tablename__ = "document_share"
    __table_args__ = (
        UniqueConstraint("share_token", name="uq_share_token"),
        CheckConstraint("permission IN ('read','comment','edit')", name="ck_permission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    share_token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    permission: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class DocumentVersion(Base):
    __tablename__ = "document_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Comment(Base):
    __tablename__ = "comment"
    __table_args__ = (
        CheckConstraint("status IN ('pending','resolved')", name="ck_comment_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_text: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    offset_start: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_end: Mapped[int] = mapped_column(Integer, nullable=False)
    # 引用前后各约 32 字，编辑后重定位用；旧数据可为空
    context_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_suffix: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    anon_name: Mapped[str] = mapped_column(Text, nullable=False)
    # anonymous ownership key from browser localStorage; owner bypasses via X-Owner-Secret
    client_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[int] = mapped_column(Integer, default=0)
