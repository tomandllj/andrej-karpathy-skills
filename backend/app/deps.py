from __future__ import annotations

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.models import Document, DocumentShare


def require_owner(doc: Document, owner_secret: str | None) -> None:
    if not owner_secret or owner_secret != doc.owner_secret:
        raise HTTPException(status_code=403, detail="需要文档管理密钥（X-Owner-Secret）")


def get_owner_secret(x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret")) -> str | None:
    return x_owner_secret


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
