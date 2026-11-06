from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_doc_or_404, get_user_doc, is_doc_owner
from app.models import Comment, Document, DocumentShare
from app.routers.admin_auth import current_user_id
from app.settings import get_settings
from app.schemas import (
    CommentAnchorBatch,
    CommentAnchorUpdate,
    CommentCreate,
    CommentOut,
    CommentUpdate,
)
from app.utils import now_iso
from app.ws_manager import manager

router = APIRouter(prefix="/api/doc", tags=["comment"])

CONTEXT_MAX = 32


def _clip_context(value: str | None) -> str | None:
    """裁剪前后文到固定长度；空串存为 None。"""
    if value is None:
        return None
    text = value[:CONTEXT_MAX]
    return text if text else None


def _comment_to_out(c: Comment, replies: list[CommentOut] | None = None) -> CommentOut:
    return CommentOut(
        id=c.id,
        doc_id=c.doc_id,
        parent_id=c.parent_id,
        selected_text=c.selected_text,
        content=c.content,
        offset_start=c.offset_start,
        offset_end=c.offset_end,
        context_prefix=c.context_prefix,
        context_suffix=c.context_suffix,
        status=c.status,  # type: ignore[arg-type]
        anon_name=c.anon_name,
        created_at=c.created_at,
        updated_at=c.updated_at,
        client_key=None,  # never expose ownership key to others in list; front keeps own
        replies=replies or [],
    )


async def _notify_doc_owner(doc: Document, doc_id: int) -> None:
    """批注增删改后通知文档所属用户，首页据此刷新列表（oncursor 关时不推）。"""
    if doc.user_id is None or not get_settings().oncursor_enabled:
        return
    await manager.broadcast_user(doc.user_id, "user.comment_activity", {"doc_id": doc_id})


def _apply_anchor(comment: Comment, body: CommentAnchorUpdate) -> None:
    """把锚点字段写到批注上。不改修改时间，那只留给批注内容本身的变动。"""
    if body.offset_start < 0 or body.offset_end < body.offset_start:
        raise HTTPException(status_code=400, detail="偏移量无效")
    comment.offset_start = body.offset_start
    comment.offset_end = body.offset_end
    comment.selected_text = body.selected_text
    comment.context_prefix = _clip_context(body.context_prefix)
    comment.context_suffix = _clip_context(body.context_suffix)


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


def _is_owner(doc: Document, secret: str | None, user_id: int | None = None) -> bool:
    """是否创建人：持有密钥，或已登录且文档属于该账号。"""
    return is_doc_owner(doc, secret, user_id)


def _resolve_permission(
    db: Session,
    doc: Document,
    owner_secret: str | None,
    share_token: str | None,
    user_id: int | None = None,
) -> str | None:
    if _is_owner(doc, owner_secret, user_id):
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
    if user_id is not None:
        link = get_user_doc(db, user_id, doc.id)
        if link is not None:
            return link.permission  # type: ignore[return-value]
    return None


def _can_manage_comment(
    doc: Document,
    comment: Comment,
    owner_secret: str | None,
    client_key: str | None,
    user_id: int | None = None,
) -> bool:
    if _is_owner(doc, owner_secret, user_id):
        return True
    if client_key and comment.client_key and client_key == comment.client_key:
        return True
    return False


@router.get("/{doc_id}/comment", response_model=list[CommentOut])
def list_comments(doc_id: int, db: Session = Depends(get_db)):
    get_doc_or_404(db, doc_id)
    # 按正文偏移从上到下；同位置再按创建时间
    rows = (
        db.query(Comment)
        .filter(Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .order_by(Comment.offset_start.asc(), Comment.created_at.asc())
        .all()
    )
    return _tree(rows)


@router.post("/{doc_id}/comment", response_model=CommentOut)
async def create_comment(
    doc_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    doc = get_doc_or_404(db, doc_id)
    user_id = current_user_id(authorization)
    perm = _resolve_permission(db, doc, x_owner_secret, share_token, user_id)
    if perm is None:
        # owner without secret header but with ownership? already checked
        if not _is_owner(doc, x_owner_secret, user_id):
            raise HTTPException(status_code=403, detail="无权访问该文档")
        perm = "edit"
    if perm == "read":
        raise HTTPException(status_code=403, detail="只读权限不能新增批注")

    parent: Comment | None = None
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

    # 回复继承父批注锚点与前后文
    if parent is not None:
        offset_start = parent.offset_start
        offset_end = parent.offset_end
        selected_text = parent.selected_text
        prefix = parent.context_prefix
        suffix = parent.context_suffix
    else:
        offset_start = body.offset_start
        offset_end = body.offset_end
        selected_text = body.selected_text
        prefix = _clip_context(body.context_prefix)
        suffix = _clip_context(body.context_suffix)

    ts = now_iso()
    comment = Comment(
        doc_id=doc_id,
        parent_id=body.parent_id,
        selected_text=selected_text,
        content=body.content,
        offset_start=offset_start,
        offset_end=offset_end,
        context_prefix=prefix,
        context_suffix=suffix,
        status="pending",
        anon_name=body.anon_name.strip() or "匿名",
        client_key=body.client_key,
        created_at=ts,
        updated_at=ts,
        is_deleted=0,
    )
    db.add(comment)
    # 中文：不改文档 updated_at，「作者提交」只反映正文保存，「评论提交」看批注 updated_at
    db.commit()
    db.refresh(comment)
    out = _comment_to_out(comment)
    await manager.broadcast(doc_id, "comment.new", out.model_dump())
    await _notify_doc_owner(doc, doc_id)
    return out


@router.put("/{doc_id}/comment/{cid}", response_model=CommentOut)
async def update_comment(
    doc_id: int,
    cid: int,
    body: CommentUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
    x_client_key: str | None = Header(default=None, alias="X-Client-Key"),
):
    doc = get_doc_or_404(db, doc_id)
    user_id = current_user_id(authorization)
    # ensure access
    perm = _resolve_permission(db, doc, x_owner_secret, share_token, user_id)
    if perm is None and not _is_owner(doc, x_owner_secret, user_id):
        raise HTTPException(status_code=403, detail="无权访问该文档")

    comment = (
        db.query(Comment)
        .filter(Comment.id == cid, Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="批注不存在")

    client_key = body.client_key or x_client_key
    is_owner = _is_owner(doc, x_owner_secret, user_id)
    wants_status = body.status is not None
    wants_edit = body.content is not None or body.anon_name is not None

    # 中文：改内容/署名仍限本人（或创建人）；标记已解决放开给所有能评论的参与者
    can_manage = _can_manage_comment(doc, comment, x_owner_secret, client_key, user_id)
    can_toggle_status = is_owner or perm in ("comment", "edit")
    if not wants_status and not wants_edit:
        # 空请求：什么都不改，原样返回
        return _comment_to_out(comment)
    if wants_edit and not can_manage:
        raise HTTPException(status_code=403, detail="只能修改自己的批注（创建人除外）")
    if wants_status and not can_toggle_status:
        raise HTTPException(status_code=403, detail="仅创建人与可评论的协作者可标记已解决")

    if body.expected_updated_at and body.expected_updated_at != comment.updated_at:
        raise HTTPException(status_code=409, detail="该批注已被他人修改，请刷新后重试")

    if wants_status:
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
    await _notify_doc_owner(doc, doc_id)
    return out


def _can_edit_content(
    doc: Document,
    owner_secret: str | None,
    share_token: str | None,
    db: Session,
    user_id: int | None = None,
) -> bool:
    """是否有权改正文（从而同步批注锚点）。"""
    if _is_owner(doc, owner_secret, user_id):
        return True
    perm = _resolve_permission(db, doc, owner_secret, share_token, user_id)
    return perm == "edit"


def _sync_reply_anchors(db: Session, root: Comment) -> None:
    """根批注锚点变更后，回复沿用同一区间。"""
    if root.parent_id is not None:
        return
    db.query(Comment).filter(
        Comment.parent_id == root.id,
        Comment.is_deleted == 0,
    ).update(
        {
            "offset_start": root.offset_start,
            "offset_end": root.offset_end,
            "selected_text": root.selected_text,
            "context_prefix": root.context_prefix,
            "context_suffix": root.context_suffix,
        }
    )


@router.put("/{doc_id}/comment/{cid}/anchor", response_model=CommentOut)
async def update_comment_anchor(
    doc_id: int,
    cid: int,
    body: CommentAnchorUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    """正文编辑后写回单条批注的起止与前后文。"""
    doc = get_doc_or_404(db, doc_id)
    if not _can_edit_content(doc, x_owner_secret, share_token, db, current_user_id(authorization)):
        raise HTTPException(status_code=403, detail="无权更新批注锚点")

    comment = (
        db.query(Comment)
        .filter(Comment.id == cid, Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="批注不存在")

    _apply_anchor(comment, body)
    _sync_reply_anchors(db, comment)
    db.commit()
    db.refresh(comment)
    out = _comment_to_out(comment)
    await manager.broadcast(doc_id, "comment.update", out.model_dump())
    return out


@router.put("/{doc_id}/comment-anchors", response_model=list[CommentOut])
async def batch_update_comment_anchors(
    doc_id: int,
    body: CommentAnchorBatch,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    """正文自动保存时批量写回仍有效的批注锚点。"""
    doc = get_doc_or_404(db, doc_id)
    if not _can_edit_content(doc, x_owner_secret, share_token, db, current_user_id(authorization)):
        raise HTTPException(status_code=403, detail="无权更新批注锚点")

    updated: list[CommentOut] = []
    for item in body.items:
        comment = (
            db.query(Comment)
            .filter(
                Comment.id == item.id,
                Comment.doc_id == doc_id,
                Comment.is_deleted == 0,
                Comment.parent_id.is_(None),
            )
            .first()
        )
        if not comment:
            continue
        _apply_anchor(comment, item)
        _sync_reply_anchors(db, comment)
        updated.append(_comment_to_out(comment))
    db.commit()
    for out in updated:
        await manager.broadcast(doc_id, "comment.update", out.model_dump())
    return updated


@router.delete("/{doc_id}/comment/{cid}")
async def delete_comment(
    doc_id: int,
    cid: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
    x_client_key: str | None = Header(default=None, alias="X-Client-Key"),
):
    doc = get_doc_or_404(db, doc_id)
    user_id = current_user_id(authorization)
    perm = _resolve_permission(db, doc, x_owner_secret, share_token, user_id)
    if perm is None and not _is_owner(doc, x_owner_secret, user_id):
        raise HTTPException(status_code=403, detail="无权访问该文档")

    comment = (
        db.query(Comment)
        .filter(Comment.id == cid, Comment.doc_id == doc_id, Comment.is_deleted == 0)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="批注不存在")

    if not _can_manage_comment(doc, comment, x_owner_secret, x_client_key, user_id):
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
    await _notify_doc_owner(doc, doc_id)
    return {"ok": True}
