from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import (
    get_active_share,
    get_doc_or_404,
    require_owner,
    require_share_access,
    share_recipient_ids,
)
from app.models import AppUser, DocumentShare, ShareRecipient, UserDoc
from app.routers.admin_auth import current_user_id, require_user_id
from app.schemas import DocOut, ShareCreate, ShareOut, ShareUpdate
from app.utils import gen_share_token, now_iso

router = APIRouter(tags=["share"])


def _share_out(db: Session, share: DocumentShare) -> ShareOut:
    """把分享行转成输出；带上接收人用户名，空列表表示不限定。"""
    recipient_ids = sorted(share_recipient_ids(db, share.id))
    names: list[str] = []
    if recipient_ids:
        rows = db.query(AppUser).filter(AppUser.id.in_(recipient_ids)).all()
        by_id = {row.id: row.username for row in rows}
        names = [by_id.get(uid, "未知") for uid in recipient_ids]
    return ShareOut(
        id=share.id,
        doc_id=share.doc_id,
        share_token=share.share_token,
        permission=share.permission,  # type: ignore[arg-type]
        is_active=share.is_active,
        created_at=share.created_at,
        share_url_path=f"/s/{share.share_token}",
        recipients=names,
    )


def _deliver_to_recipients(db: Session, doc, share: DocumentShare, recipient_ids: list[int]) -> None:
    """站内投递：把文档直接写进每个接收人的「收到的」（未归类），并标「新」。

    接收人刷新首页即可看到；已有的收件记录只更新权限并重新标「新」。
    """
    ts = now_iso()
    for uid in recipient_ids:
        if doc.user_id == uid:
            continue  # 分给创建人自己：文档本来就在他的列表里
        row = (
            db.query(UserDoc)
            .filter(UserDoc.user_id == uid, UserDoc.doc_id == doc.id)
            .first()
        )
        if row is None:
            db.add(
                UserDoc(
                    user_id=uid,
                    doc_id=doc.id,
                    folder_id=None,
                    permission=share.permission,
                    is_new=1,
                    created_at=ts,
                    updated_at=ts,
                )
            )
        else:
            row.permission = share.permission
            row.is_new = 1
            row.updated_at = ts


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

    # 接收人必须真实存在；管理员固定身份和文档主人不算接收人
    if body.recipient_ids:
        rows = db.query(AppUser).filter(AppUser.id.in_(body.recipient_ids)).all()
        found = {row.id for row in rows}
        if any(uid not in found for uid in body.recipient_ids):
            raise HTTPException(status_code=400, detail="部分接收人不存在")

    share = DocumentShare(
        doc_id=doc.id,
        share_token=gen_share_token(),
        permission=body.permission,
        is_active=1,
        created_at=now_iso(),
    )
    db.add(share)
    db.flush()
    ts = now_iso()
    for uid in body.recipient_ids:
        db.add(ShareRecipient(share_id=share.id, user_id=uid, created_at=ts))
    _deliver_to_recipients(db, doc, share, body.recipient_ids)
    db.commit()
    db.refresh(share)
    return _share_out(db, share)


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
    return [_share_out(db, r) for r in rows]


@router.get("/api/share/{token}", response_model=DocOut)
def access_by_token(
    token: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    share = get_active_share(db, token)
    # 限接收人的非只读分享：匿名或非接收人直接 403，不暴露内容
    require_share_access(db, share, current_user_id(authorization))
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
    return _share_out(db, share)


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
    """已登录的人打开分享链接后，把这篇记进他的「收到的」；已有归类不动，只更新权限。

    指定了接收人的分享：只有接收人能记进「收到的」，其他人只是临时看；不动「新」标记。
    """
    user_id = require_user_id(authorization)
    share = get_active_share(db, token)  # 分享已关闭则 404
    doc = get_doc_or_404(db, share.doc_id)
    if doc.user_id == user_id:
        # 分回给创建人自己：文档本来就在他的列表里
        return {"ok": True, "owned": True}
    recipient_ids = share_recipient_ids(db, share.id)
    if recipient_ids and user_id not in recipient_ids:
        # 非接收人不记进「收到的」，也不报错，本次仍按分享权限看
        return {"ok": False, "restricted": True}
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
