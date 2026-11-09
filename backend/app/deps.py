from __future__ import annotations

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare, ShareRecipient, UserDoc


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


def share_recipient_ids(db: Session, share_id: int) -> set[int]:
    """取一条分享指定的全部接收人编号；空集合表示不限定。"""
    rows = db.query(ShareRecipient).filter(ShareRecipient.share_id == share_id).all()
    return {row.user_id for row in rows}


def require_share_access(db: Session, share: DocumentShare, user_id: int | None) -> None:
    """分享指定了接收人且权限非只读时，要求登录者是接收人之一，否则 403。

    只读分享豁免：匿名也能看（规则：所有只读链接免登录可查看）。
    """
    if share.permission == "read":
        return
    ids = share_recipient_ids(db, share.id)
    if not ids:
        return
    if user_id is None or user_id not in ids:
        raise HTTPException(status_code=403, detail="该分享仅限指定接收人，请登录后查看")


def get_doc_or_404(db: Session, doc_id: int, include_deleted: bool = False) -> Document:
    q = db.query(Document).filter(Document.id == doc_id)
    if not include_deleted:
        q = q.filter(Document.is_deleted == 0)
    doc = q.first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc
