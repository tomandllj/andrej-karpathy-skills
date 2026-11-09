from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.database import ADMIN_DB_USERNAME, get_db
from app.deps import get_doc_or_404, get_user_doc, is_doc_owner, require_owner, require_share_access
from app.models import AppUser, Comment, Document, DocumentShare, DocumentVersion, Folder, UserDoc
from app.routers.admin_auth import current_user_id, require_user_id
from app.schemas import (
    ClaimLegacyIn,
    ClaimLegacyOut,
    DocBatchRequest,
    DocCreate,
    DocSearchRequest,
    DocCreateOut,
    DocListItem,
    DocMoveIn,
    DocOut,
    DocUpdate,
    MineDocItem,
    VersionDetail,
    VersionOut,
)
from app.utils import gen_secret, now_iso

router = APIRouter(prefix="/api/doc", tags=["document"])


def _is_owner(doc: Document, secret: str | None, user_id: int | None = None) -> bool:
    """是否创建人：持有密钥，或已登录且文档属于该账号。"""
    return is_doc_owner(doc, secret, user_id)


def _owner_name(db: Session, doc: Document) -> str | None:
    """取文档创建者的用户名；匿名时期的旧文档返回 None；管理员显示为「管理员」。"""
    if doc.user_id is None:
        return None
    row = db.get(AppUser, doc.user_id)
    if not row:
        return None
    if row.username == ADMIN_DB_USERNAME:
        return "管理员"
    return row.username


def _resolve_edit_permission(
    db: Session,
    doc: Document,
    owner_secret: str | None,
    share_token: str | None,
    user_id: int | None = None,
) -> tuple[bool, str | None]:
    """Return (can_edit_content, effective_permission). Owner always can edit."""
    if _is_owner(doc, owner_secret, user_id):
        return True, "edit"
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
            # 限接收人的分享：非接收人拿不到编辑权限
            require_share_access(db, share, user_id)
            return share.permission == "edit", share.permission
    if user_id is not None:
        link = get_user_doc(db, user_id, doc.id)
        if link is not None:
            return link.permission == "edit", link.permission  # type: ignore[return-value]
    return False, None


def _owned_folder(db: Session, user_id: int, folder_id: int) -> Folder:
    """取出当前用户的文件夹，不是自己的则拒绝。"""
    folder = (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.user_id == user_id)
        .first()
    )
    if folder is None:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    return folder


@router.post("", response_model=DocCreateOut)
def create_doc(
    body: DocCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """创建文档；已登录时记下所属用户，并可选放入自己的文件夹。"""
    ts = now_iso()
    secret = gen_secret()
    user_id = current_user_id(authorization)
    folder_id = body.folder_id
    if folder_id is not None:
        if user_id is None:
            raise HTTPException(status_code=401, detail="未登录或会话已过期")
        _owned_folder(db, user_id, folder_id)
    doc = Document(
        owner_secret=secret,
        title=body.title or "无标题文档",
        content=body.content or "",
        created_at=ts,
        updated_at=ts,
        is_deleted=0,
        user_id=user_id,
        folder_id=folder_id,
    )
    db.add(doc)
    db.flush()
    # initial version snapshot
    ver = DocumentVersion(
        doc_id=doc.id,
        version_no=1,
        content_snapshot=doc.content,
        remark="初始版本",
        created_at=ts,
    )
    db.add(ver)
    db.commit()
    db.refresh(doc)
    return DocCreateOut(
        id=doc.id,
        owner_secret=secret,
        title=doc.title,
        content=doc.content,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _root_comment_stats(db: Session, doc_ids: list[int]) -> dict[int, tuple[int, int]]:
    """统计每篇文档未删除的根批注数，以及其中已解决的数量。"""
    if not doc_ids:
        return {}
    rows = (
        db.query(
            Comment.doc_id,
            func.count(Comment.id),
            func.sum(case((Comment.status == "resolved", 1), else_=0)),
        )
        .filter(
            Comment.doc_id.in_(doc_ids),
            Comment.is_deleted == 0,
            Comment.parent_id.is_(None),
        )
        .group_by(Comment.doc_id)
        .all()
    )
    return {
        int(doc_id): (int(total or 0), int(resolved or 0))
        for doc_id, total, resolved in rows
    }


def _pending_comment_texts(db: Session, doc_ids: list[int]) -> dict[int, list[str]]:
    """按文档收集未解决根批注的正文，顺序按批注编号。"""
    if not doc_ids:
        return {}
    rows = (
        db.query(Comment.doc_id, Comment.content)
        .filter(
            Comment.doc_id.in_(doc_ids),
            Comment.is_deleted == 0,
            Comment.parent_id.is_(None),
            Comment.status == "pending",
        )
        .order_by(Comment.id.asc())
        .all()
    )
    grouped: dict[int, list[str]] = {}
    for doc_id, content in rows:
        text = (content or "").strip()
        if not text:
            continue
        grouped.setdefault(int(doc_id), []).append(text)
    return grouped


def _latest_comments(db: Session, doc_ids: list[int]) -> dict[int, tuple[str, str]]:
    """取出每个文档最近活动过的未删除批注的署名和更新时间（含修改，不只创建）。"""
    if not doc_ids:
        return {}
    rows = (
        db.query(Comment.doc_id, Comment.anon_name, Comment.updated_at)
        .filter(Comment.doc_id.in_(doc_ids), Comment.is_deleted == 0)
        .order_by(Comment.updated_at.desc(), Comment.id.desc())
        .all()
    )
    latest: dict[int, tuple[str, str]] = {}
    for doc_id, anon_name, updated_at in rows:
        key = int(doc_id)
        if key in latest:
            continue
        name = (anon_name or "").strip() or "匿名"
        latest[key] = (name, updated_at)
    return latest


def _shared_doc_ids(db: Session, doc_ids: list[int]) -> set[int]:
    """找出这些文档里仍有有效分享链接的编号。"""
    if not doc_ids:
        return set()
    rows = (
        db.query(DocumentShare.doc_id)
        .filter(DocumentShare.doc_id.in_(doc_ids), DocumentShare.is_active == 1)
        .distinct()
        .all()
    )
    return {int(doc_id) for (doc_id,) in rows}


def _content_size(content: str | None) -> int:
    """按 UTF-8 字节数计算正文字节大小。"""
    return len((content or "").encode("utf-8"))


def _sub_lines(content: str | None) -> str:
    """取正文第 2、第 3 条有文字的行，作为列表副标题。"""
    lines: list[str] = []
    for line in (content or "").splitlines():
        text = line.strip()
        if not text:
            continue
        lines.append(text)
        if len(lines) >= 3:
            break
    return "\n".join(lines[1:3])


@router.post("/list", response_model=list[DocListItem])
def list_docs(body: DocBatchRequest, db: Session = Depends(get_db)):
    """按编号返回文档列表，附带批注数、最新批注和是否已分享。"""
    if not body.ids:
        return []
    rows = (
        db.query(Document)
        .filter(Document.id.in_(body.ids), Document.is_deleted == 0)
        .order_by(Document.updated_at.desc())
        .all()
    )
    doc_ids = [r.id for r in rows]
    stats = _root_comment_stats(db, doc_ids)
    pending_texts = _pending_comment_texts(db, doc_ids)
    shared_ids = _shared_doc_ids(db, doc_ids)
    latest = _latest_comments(db, doc_ids)
    return [
        DocListItem(
            id=r.id,
            title=r.title,
            updated_at=r.updated_at,
            created_at=r.created_at,
            is_deleted=r.is_deleted,
            folder_id=r.folder_id,
            comment_count=stats.get(r.id, (0, 0))[0],
            resolved_count=stats.get(r.id, (0, 0))[1],
            pending_comments=pending_texts.get(r.id, []),
            content_size=_content_size(r.content),
            sub_lines=_sub_lines(r.content),
            is_shared=r.id in shared_ids,
            latest_comment_anon_name=latest.get(r.id, (None, None))[0],
            latest_comment_at=latest.get(r.id, (None, None))[1],
        )
        for r in rows
    ]


@router.post("/search", response_model=list[int])
def search_docs(body: DocSearchRequest, db: Session = Depends(get_db)):
    """在给定文档的标题、正文和批注里查找关键字，返回命中的编号。"""
    q = (body.q or "").strip().lower()
    if not body.ids or not q:
        return []
    rows = (
        db.query(Document.id, Document.title, Document.content)
        .filter(Document.id.in_(body.ids), Document.is_deleted == 0)
        .all()
    )
    hit = {
        int(row.id)
        for row in rows
        if q in (row.title or "").lower() or q in (row.content or "").lower()
    }
    alive = {int(row.id) for row in rows}
    if not alive:
        return []
    comments = (
        db.query(Comment.doc_id, Comment.content, Comment.selected_text)
        .filter(Comment.doc_id.in_(alive), Comment.is_deleted == 0)
        .all()
    )
    for doc_id, content, selected in comments:
        if q in (content or "").lower() or q in (selected or "").lower():
            hit.add(int(doc_id))
    return list(hit)


def _doc_list_item(
    doc: Document,
    stats: dict[int, tuple[int, int]],
    pending_texts: dict[int, list[str]],
    shared_ids: set[int],
    latest: dict[int, tuple[str, str]],
    origin: str = "owned",
    from_name: str | None = None,
    folder_id: int | None = None,
    is_new: bool = False,
) -> MineDocItem:
    """把文档行转成首页「我的文档」条目，附带批注统计与归属信息。"""
    return MineDocItem(
        id=doc.id,
        title=doc.title,
        updated_at=doc.updated_at,
        created_at=doc.created_at,
        is_deleted=doc.is_deleted,
        folder_id=folder_id,
        comment_count=stats.get(doc.id, (0, 0))[0],
        resolved_count=stats.get(doc.id, (0, 0))[1],
        pending_comments=pending_texts.get(doc.id, []),
        content_size=_content_size(doc.content),
        sub_lines=_sub_lines(doc.content),
        is_shared=doc.id in shared_ids,
        latest_comment_anon_name=latest.get(doc.id, (None, None))[0],
        latest_comment_at=latest.get(doc.id, (None, None))[1],
        origin=origin,
        from_name=from_name,
        is_new=is_new,
    )


@router.get("/mine", response_model=list[MineDocItem])
def my_docs(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """当前账号的文档：自己创建的 + 收到的分享，统一按修改时间倒序。"""
    user_id = require_user_id(authorization)
    owned_rows = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.is_deleted == 0)
        .all()
    )
    received_rows = (
        db.query(UserDoc, Document, AppUser.username)
        .join(Document, Document.id == UserDoc.doc_id)
        .outerjoin(AppUser, AppUser.id == Document.user_id)
        .filter(
            UserDoc.user_id == user_id,
            Document.is_deleted == 0,
            or_(Document.user_id.is_(None), Document.user_id != user_id),
        )
        .all()
    )

    # 逐条记下归属和各自行内的文件夹，再统一算批注统计
    entries: list[tuple[Document, str, str | None, int | None, bool]] = [
        (doc, "owned", None, doc.folder_id, False) for doc in owned_rows
    ]
    for link, doc, owner_name in received_rows:
        entries.append(
            (doc, "received", owner_name or "未知", link.folder_id, bool(link.is_new))
        )

    entries.sort(key=lambda e: e[0].updated_at, reverse=True)
    doc_ids = [doc.id for doc, *_ in entries]
    stats = _root_comment_stats(db, doc_ids)
    pending_texts = _pending_comment_texts(db, doc_ids)
    shared_ids = _shared_doc_ids(db, doc_ids)
    latest = _latest_comments(db, doc_ids)
    return [
        _doc_list_item(
            doc,
            stats,
            pending_texts,
            shared_ids,
            latest,
            origin=origin,
            from_name=from_name,
            folder_id=folder_id,
            is_new=is_new,
        )
        for doc, origin, from_name, folder_id, is_new in entries
    ]


@router.post("/claim-legacy", response_model=ClaimLegacyOut)
def claim_legacy(
    body: ClaimLegacyIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """把本机持有密钥、库里还没有归属的旧文档绑定到当前账号。"""
    user_id = require_user_id(authorization)
    claimed = 0
    for item in body.items:
        doc = db.query(Document).filter(Document.id == item.id).first()
        if doc is None or doc.is_deleted or doc.user_id is not None:
            continue
        if not item.owner_secret or item.owner_secret != doc.owner_secret:
            continue
        doc.user_id = user_id
        claimed += 1
    db.commit()
    return ClaimLegacyOut(claimed=claimed)


@router.get("/{doc_id}", response_model=DocOut)
def get_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    doc = get_doc_or_404(db, doc_id)
    user_id = current_user_id(authorization)
    owner = _is_owner(doc, x_owner_secret, user_id)
    permission = "edit" if owner else None
    share_id = None
    token_out = None
    origin = "owned" if owner else None
    from_name = None
    # 文件夹按当前视角返回：自己的文档看 document.folder_id，收到的看 user_doc.folder_id
    folder_out = doc.folder_id
    if not owner and share_token:
        share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.doc_id == doc.id,
                DocumentShare.share_token == share_token,
                DocumentShare.is_active == 1,
            )
            .first()
        )
        if not share:
            raise HTTPException(status_code=403, detail="无权访问该文档")
        # 限接收人的非只读分享：非接收人打不开
        require_share_access(db, share, user_id)
        permission = share.permission
        share_id = share.id
        token_out = share.share_token
    elif not owner and user_id is not None:
        link = get_user_doc(db, user_id, doc.id)
        if link is not None:
            # 收件人从首页打开：沿用打开分享时的权限，文件夹按他自己的归类
            permission = link.permission  # type: ignore[assignment]
            origin = "received"
            from_name = _owner_name(db, doc)
            folder_out = link.folder_id

    # 收件人打开文档即视为已读（无论从首页还是分享链接进来），清掉「新」标记
    if not owner and user_id is not None:
        link = get_user_doc(db, user_id, doc.id)
        if link is not None and link.is_new:
            link.is_new = 0
            db.commit()

    return DocOut(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        is_owner=owner,
        permission=permission,
        share_id=share_id,
        share_token=token_out,
        folder_id=folder_out,
        origin=origin,
        from_name=from_name,
    )


@router.put("/{doc_id}", response_model=DocOut)
def update_doc(
    doc_id: int,
    body: DocUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    doc = get_doc_or_404(db, doc_id)
    user_id = current_user_id(authorization)
    can_edit, perm = _resolve_edit_permission(db, doc, x_owner_secret, share_token, user_id)
    if not can_edit:
        raise HTTPException(status_code=403, detail="当前权限不允许修改正文（需要 edit 或创建人）")

    content_changed = body.content is not None and body.content != doc.content
    if body.title is not None:
        doc.title = body.title
    if body.content is not None:
        doc.content = body.content
    doc.updated_at = now_iso()

    if content_changed:
        max_no = (
            db.query(func.max(DocumentVersion.version_no))
            .filter(DocumentVersion.doc_id == doc.id)
            .scalar()
            or 0
        )
        db.add(
            DocumentVersion(
                doc_id=doc.id,
                version_no=max_no + 1,
                content_snapshot=doc.content,
                remark=body.remark,
                created_at=doc.updated_at,
            )
        )

    db.commit()
    db.refresh(doc)
    return DocOut(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        is_owner=_is_owner(doc, x_owner_secret, user_id),
        permission=perm or ("edit" if _is_owner(doc, x_owner_secret, user_id) else None),
        folder_id=doc.folder_id,
    )


@router.put("/{doc_id}/folder")
def move_doc_folder(
    doc_id: int,
    body: DocMoveIn,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    """把文档归到自己的文件夹：自己的文档改 document，收到的只改自己的归类，不动原文。"""
    user_id = current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    doc = get_doc_or_404(db, doc_id)
    link = get_user_doc(db, user_id, doc.id)
    if body.folder_id is not None:
        # 目标文件夹必须属于当前账号
        _owned_folder(db, user_id, body.folder_id)
    if doc.user_id == user_id or (doc.user_id is None and _is_owner(doc, x_owner_secret)):
        # 自己的文档；匿名时期的旧文档首次操作时顺便绑定账号
        if doc.user_id is None:
            doc.user_id = user_id
        doc.folder_id = body.folder_id
    elif link is not None:
        link.folder_id = body.folder_id
        link.updated_at = now_iso()
    elif _is_owner(doc, x_owner_secret):
        # 旧流程：只凭密钥也能移动
        doc.folder_id = body.folder_id
    else:
        raise HTTPException(status_code=403, detail="无权移动该文档")
    db.commit()
    return {"ok": True, "folder_id": body.folder_id}


@router.delete("/{doc_id}")
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    """自己的文档软删除并关掉分享；收到的文档只是从自己的列表移除，原文保留。"""
    user_id = current_user_id(authorization)
    doc = get_doc_or_404(db, doc_id)
    link = get_user_doc(db, user_id, doc.id) if user_id is not None else None
    if user_id is not None and doc.user_id == user_id:
        pass  # 创建人删除
    elif link is not None:
        db.delete(link)
        db.commit()
        return {"ok": True, "removed": True}
    elif not _is_owner(doc, x_owner_secret):
        raise HTTPException(status_code=403, detail="无权删除该文档")
    doc.is_deleted = 1
    doc.updated_at = now_iso()
    # deactivate shares
    db.query(DocumentShare).filter(DocumentShare.doc_id == doc.id).update({"is_active": 0})
    # 收到这篇的人的列表里也随之消失
    db.query(UserDoc).filter(UserDoc.doc_id == doc.id).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "removed": False}


@router.get("/{doc_id}/version", response_model=list[VersionOut])
def list_versions(doc_id: int, db: Session = Depends(get_db)):
    get_doc_or_404(db, doc_id)
    rows = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.doc_id == doc_id)
        .order_by(DocumentVersion.version_no.desc())
        .all()
    )
    return [
        VersionOut(
            id=r.id,
            doc_id=r.doc_id,
            version_no=r.version_no,
            remark=r.remark,
            created_at=r.created_at,
            content_preview=(r.content_snapshot[:120] + "…")
            if len(r.content_snapshot) > 120
            else r.content_snapshot,
        )
        for r in rows
    ]


@router.get("/{doc_id}/version/{vid}", response_model=VersionDetail)
def get_version(doc_id: int, vid: int, db: Session = Depends(get_db)):
    get_doc_or_404(db, doc_id)
    ver = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.id == vid, DocumentVersion.doc_id == doc_id)
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="版本不存在")
    return VersionDetail(
        id=ver.id,
        doc_id=ver.doc_id,
        version_no=ver.version_no,
        content_snapshot=ver.content_snapshot,
        remark=ver.remark,
        created_at=ver.created_at,
    )


@router.post("/{doc_id}/rollback/{vid}", response_model=DocOut)
def rollback(
    doc_id: int,
    vid: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    doc = get_doc_or_404(db, doc_id)
    require_owner(doc, x_owner_secret, current_user_id(authorization))
    ver = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.id == vid, DocumentVersion.doc_id == doc_id)
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="版本不存在")
    doc.content = ver.content_snapshot
    doc.updated_at = now_iso()
    max_no = (
        db.query(func.max(DocumentVersion.version_no))
        .filter(DocumentVersion.doc_id == doc.id)
        .scalar()
        or 0
    )
    db.add(
        DocumentVersion(
            doc_id=doc.id,
            version_no=max_no + 1,
            content_snapshot=doc.content,
            remark=f"回滚到版本 {ver.version_no}",
            created_at=doc.updated_at,
        )
    )
    db.commit()
    db.refresh(doc)
    return DocOut(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        is_owner=True,
        permission="edit",
        folder_id=doc.folder_id,
    )


@router.get("/{doc_id}/export")
def export_md(doc_id: int, db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, doc_id)
    filename = f"{doc.title or 'document'}.md".replace("/", "_")
    return PlainTextResponse(
        content=doc.content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
