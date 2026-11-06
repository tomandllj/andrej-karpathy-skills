from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_active_share, get_doc_or_404, require_owner
from app.models import DocumentShare, UserDoc
from app.routers.admin_auth import current_user_id, require_user_id
from app.schemas import DocOut, ShareCreate, ShareOut, ShareUpdate
from app.utils import gen_share_token, now_iso

router = APIRouter(tags=["share"])


def _share_out(share: DocumentShare) -> ShareOut:
    return ShareOut(
        id=share.id,
        doc_id=share.doc_id,
        share_token=share.share_token,
        permission=share.permission,  # type: ignore[arg-type]
        is_active=share.is_active,
        created_at=share.created_at,
        share_url_path=f"/s/{share.share_token}",
    )


@router.post("/api/doc/{doc_id}/share", response_model=ShareOut)
def create_share(
    doc_id: int,
    body: ShareCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    doc = get_doc_or_404(db, doc_id)
    require_owner(doc, x_owner_secret, current_user_id(authorization))
    share = DocumentShare(
        doc_id=doc.id,
        share_token=gen_share_token(),
        permission=body.permission,
        is_active=1,
        created_at=now_iso(),
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return _share_out(share)


@router.get("/api/doc/{doc_id}/share", response_model=list[ShareOut])
def list_shares(
    doc_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    doc = get_doc_or_404(db, doc_id)
    require_owner(doc, x_owner_secret, current_user_id(authorization))
    rows = (
        db.query(DocumentShare)
        .filter(DocumentShare.doc_id == doc_id)
        .order_by(DocumentShare.id.desc())
        .all()
    )
    return [_share_out(r) for r in rows]


@router.get("/api/share/{token}", response_model=DocOut)
def access_by_token(token: str, db: Session = Depends(get_db)):
    share = get_active_share(db, token)
    doc = get_doc_or_404(db, share.doc_id)
    return DocOut(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        is_owner=False,
        permission=share.permission,  # type: ignore[arg-type]
        share_id=share.id,
        share_token=share.share_token,
    )


@router.put("/api/share/{share_id}", response_model=ShareOut)
def update_share(
    share_id: int,
    body: ShareUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    share = db.query(DocumentShare).filter(DocumentShare.id == share_id).first()
    if not share:
        raise HTTPException(status_code=404, detail="分享记录不存在")
    doc = get_doc_or_404(db, share.doc_id, include_deleted=True)
    require_owner(doc, x_owner_secret, current_user_id(authorization))
    if body.permission is not None:
        share.permission = body.permission
    if body.is_active is not None:
        share.is_active = 1 if body.is_active else 0
    db.commit()
    db.refresh(share)
    return _share_out(share)


@router.delete("/api/share/{share_id}")
def delete_share(
    share_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    share = db.query(DocumentShare).filter(DocumentShare.id == share_id).first()
    if not share:
        raise HTTPException(status_code=404, detail="分享记录不存在")
    doc = get_doc_or_404(db, share.doc_id, include_deleted=True)
    require_owner(doc, x_owner_secret, current_user_id(authorization))
    share.is_active = 0
    db.commit()
    return {"ok": True}


@router.post("/api/share/{token}/save")
def save_shared_doc(
    token: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """已登录的人打开分享链接后，把这篇记进他的「收到的」；已有归类不动，只更新权限。"""
    user_id = require_user_id(authorization)
    share = get_active_share(db, token)  # 分享已关闭则 404
    doc = get_doc_or_404(db, share.doc_id)
    if doc.user_id == user_id:
        # 分回给创建人自己：文档本来就在他的列表里
        return {"ok": True, "owned": True}
    row = (
        db.query(UserDoc)
        .filter(UserDoc.user_id == user_id, UserDoc.doc_id == doc.id)
        .first()
    )
    ts = now_iso()
    if row is None:
        row = UserDoc(
            user_id=user_id,
            doc_id=doc.id,
            folder_id=None,
            permission=share.permission,
            created_at=ts,
            updated_at=ts,
        )
        db.add(row)
    else:
        row.permission = share.permission
        row.updated_at = ts
    db.commit()
    return {"ok": True, "owned": False}
