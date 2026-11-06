from __future__ import annotations

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare, UserDoc


def is_doc_owner(doc: Document, owner_secret: str | None, user_id: int | None = None) -> bool:
    """是否创建人：持有密钥，或已登录且文档属于该账号。"""
    if owner_secret and owner_secret == doc.owner_secret:
        return True
    return user_id is not None and doc.user_id == user_id


def require_owner(doc: Document, owner_secret: str | None, user_id: int | None = None) -> None:
    """要求是创建人（密钥或登录身份），否则 403。"""
    if not is_doc_owner(doc, owner_secret, user_id):
        raise HTTPException(status_code=403, detail="无权管理该文档（需要创建人或密钥）")


def get_owner_secret(x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret")) -> str | None:
    return x_owner_secret


def get_user_doc(db: Session, user_id: int, doc_id: int) -> UserDoc | None:
    """取当前用户收到某篇文档的记录；没有则 None。"""
    return (
        db.query(UserDoc)
        .filter(UserDoc.user_id == user_id, UserDoc.doc_id == doc_id)
        .first()
    )


def get_active_share(db: Session, token: str) -> DocumentShare:
    share = (
        db.query(DocumentShare)
        .filter(DocumentShare.share_token == token, DocumentShare.is_active == 1)
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="分享链接无效或已关闭")
    return share


def get_doc_or_404(db: Session, doc_id: int, include_deleted: bool = False) -> Document:
    q = db.query(Document).filter(Document.id == doc_id)
    if not include_deleted:
        q = q.filter(Document.is_deleted == 0)
    doc = q.first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc
