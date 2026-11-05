from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_doc_or_404
from app.models import Comment, Document, DocumentShare
from app.schemas import CommentCreate, CommentOut, CommentUpdate
from app.utils import now_iso
from app.ws_manager import manager

router = APIRouter(prefix="/api/doc", tags=["comment"])


def _comment_to_out(c: Comment, replies: list[CommentOut] | None = None) -> CommentOut:
    return CommentOut(
        id=c.id,
        doc_id=c.doc_id,
        parent_id=c.parent_id,
        selected_text=c.selected_text,
        content=c.content,
        offset_start=c.offset_start,
        offset_end=c.offset_end,
        status=c.status,  # type: ignore[arg-type]
        anon_name=c.anon_name,
        created_at=c.created_at,
        updated_at=c.updated_at,
        client_key=None,  # never expose ownership key to others in list; front keeps own
        replies=replies or [],
    )


def _tree(comments: list[Comment]) -> list[CommentOut]:
    by_parent: dict[int | None, list[Comment]] = {}
    for c in comments:
        by_parent.setdefault(c.parent_id, []).append(c)
    roots = by_parent.get(None, [])
    result: list[CommentOut] = []
    for root in roots:
        replies = [_comment_to_out(r) for r in by_parent.get(root.id, [])]
        result.append(_comment_to_out(root, replies))
    return result


def _is_owner(doc: Document, secret: str | None) -> bool:
    return bool(secret and secret == doc.owner_secret)


def _resolve_permission(
    db: Session,
    doc: Document,
    owner_secret: str | None,
    share_token: str | None,
) -> str | None:
    if _is_owner(doc, owner_secret):
        return "edit"
    if share_token:
        share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.doc_id == doc.id,
                DocumentShare.share_token == share_token,
                DocumentShare.is_active == 1,
            )
            .first()
        )
        if share:
            return share.permission
    return None


def _can_manage_comment(
    doc: Document,
    comment: Comment,
    owner_secret: str | None,
    client_key: str | None,
) -> bool:
    if _is_owner(doc, owner_secret):
        return True
    if client_key and comment.client_key and client_key == comment.client_key:
        return True
    return False


@router.get("/{doc_id}/comment", response_model=list[CommentOut])
def list_comments(doc_id: int, db: Session = Depends(get_db)):
    get_doc_or_404(db, doc_id)
    rows = (
        db.query(Comment)
        .filter(Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return _tree(rows)


@router.post("/{doc_id}/comment", response_model=CommentOut)
async def create_comment(
    doc_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    doc = get_doc_or_404(db, doc_id)
    perm = _resolve_permission(db, doc, x_owner_secret, share_token)
    if perm is None:
        # owner without secret header but with ownership? already checked
        if not _is_owner(doc, x_owner_secret):
            raise HTTPException(status_code=403, detail="无权访问该文档")
        perm = "edit"
    if perm == "read":
        raise HTTPException(status_code=403, detail="只读权限不能新增批注")

    if body.parent_id is not None:
        parent = (
            db.query(Comment)
            .filter(
                Comment.id == body.parent_id,
                Comment.doc_id == doc_id,
                Comment.is_deleted == 0,
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=404, detail="父批注不存在")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="仅支持一级回复")

    if body.offset_start < 0 or body.offset_end < body.offset_start:
        raise HTTPException(status_code=400, detail="偏移量无效")

    ts = now_iso()
    comment = Comment(
        doc_id=doc_id,
        parent_id=body.parent_id,
        selected_text=body.selected_text,
        content=body.content,
        offset_start=body.offset_start,
        offset_end=body.offset_end,
        status="pending",
        anon_name=body.anon_name.strip() or "匿名",
        client_key=body.client_key,
        created_at=ts,
        updated_at=ts,
        is_deleted=0,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    out = _comment_to_out(comment)
    await manager.broadcast(doc_id, "comment.new", out.model_dump())
    return out


@router.put("/{doc_id}/comment/{cid}", response_model=CommentOut)
async def update_comment(
    doc_id: int,
    cid: int,
    body: CommentUpdate,
    db: Session = Depends(get_db),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
    x_client_key: str | None = Header(default=None, alias="X-Client-Key"),
):
    doc = get_doc_or_404(db, doc_id)
    # ensure access
    perm = _resolve_permission(db, doc, x_owner_secret, share_token)
    if perm is None and not _is_owner(doc, x_owner_secret):
        raise HTTPException(status_code=403, detail="无权访问该文档")

    comment = (
        db.query(Comment)
        .filter(Comment.id == cid, Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="批注不存在")

    client_key = body.client_key or x_client_key
    is_owner = _is_owner(doc, x_owner_secret)
    if not _can_manage_comment(doc, comment, x_owner_secret, client_key):
        raise HTTPException(status_code=403, detail="只能修改自己的批注（创建人除外）")

    if body.status is not None:
        if not is_owner:
            raise HTTPException(status_code=403, detail="仅创建人可标记已解决")
        comment.status = body.status
    if body.content is not None:
        comment.content = body.content
    if body.anon_name is not None:
        comment.anon_name = body.anon_name
    comment.updated_at = now_iso()
    db.commit()
    db.refresh(comment)
    out = _comment_to_out(comment)
    await manager.broadcast(doc_id, "comment.update", out.model_dump())
    return out


@router.delete("/{doc_id}/comment/{cid}")
async def delete_comment(
    doc_id: int,
    cid: int,
    db: Session = Depends(get_db),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
    x_client_key: str | None = Header(default=None, alias="X-Client-Key"),
):
    doc = get_doc_or_404(db, doc_id)
    perm = _resolve_permission(db, doc, x_owner_secret, share_token)
    if perm is None and not _is_owner(doc, x_owner_secret):
        raise HTTPException(status_code=403, detail="无权访问该文档")

    comment = (
        db.query(Comment)
        .filter(Comment.id == cid, Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="批注不存在")

    if not _can_manage_comment(doc, comment, x_owner_secret, x_client_key):
        raise HTTPException(status_code=403, detail="只能删除自己的批注（创建人除外）")

    comment.is_deleted = 1
    comment.updated_at = now_iso()
    # soft-delete replies of a root
    if comment.parent_id is None:
        db.query(Comment).filter(
            Comment.parent_id == comment.id, Comment.is_deleted == 0
        ).update({"is_deleted": 1, "updated_at": comment.updated_at})
    db.commit()
    await manager.broadcast(doc_id, "comment.delete", {"id": cid, "doc_id": doc_id})
    return {"ok": True}
