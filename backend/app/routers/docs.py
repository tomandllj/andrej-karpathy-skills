from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_doc_or_404, require_owner
from app.models import Document, DocumentShare, DocumentVersion
from app.schemas import (
    DocBatchRequest,
    DocCreate,
    DocCreateOut,
    DocListItem,
    DocOut,
    DocUpdate,
    VersionDetail,
    VersionOut,
)
from app.utils import gen_secret, now_iso

router = APIRouter(prefix="/api/doc", tags=["document"])


def _is_owner(doc: Document, secret: str | None) -> bool:
    return bool(secret and secret == doc.owner_secret)


def _resolve_edit_permission(
    db: Session,
    doc: Document,
    owner_secret: str | None,
    share_token: str | None,
) -> tuple[bool, str | None]:
    """Return (can_edit_content, effective_permission). Owner always can edit."""
    if _is_owner(doc, owner_secret):
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
            return share.permission == "edit", share.permission
    return False, None


@router.post("", response_model=DocCreateOut)
def create_doc(body: DocCreate, db: Session = Depends(get_db)):
    ts = now_iso()
    secret = gen_secret()
    doc = Document(
        owner_secret=secret,
        title=body.title or "无标题文档",
        content=body.content or "",
        created_at=ts,
        updated_at=ts,
        is_deleted=0,
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


@router.post("/list", response_model=list[DocListItem])
def list_docs(body: DocBatchRequest, db: Session = Depends(get_db)):
    if not body.ids:
        return []
    rows = (
        db.query(Document)
        .filter(Document.id.in_(body.ids), Document.is_deleted == 0)
        .order_by(Document.updated_at.desc())
        .all()
    )
    return [
        DocListItem(
            id=r.id,
            title=r.title,
            updated_at=r.updated_at,
            created_at=r.created_at,
            is_deleted=r.is_deleted,
        )
        for r in rows
    ]


@router.get("/{doc_id}", response_model=DocOut)
def get_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    doc = get_doc_or_404(db, doc_id)
    owner = _is_owner(doc, x_owner_secret)
    permission = "edit" if owner else None
    share_id = None
    token_out = None
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
        permission = share.permission
        share_id = share.id
        token_out = share.share_token
    elif not owner:
        # public read of meta only if no secret — still return content for owner-less open?
        # Spec: open by id for owner via localStorage; collaborators use share token.
        # Allow get without secret but mark non-owner with no permission (frontend may still show read-only if they have secret later).
        permission = None

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
    )


@router.put("/{doc_id}", response_model=DocOut)
def update_doc(
    doc_id: int,
    body: DocUpdate,
    db: Session = Depends(get_db),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
    share_token: str | None = Query(default=None),
):
    doc = get_doc_or_404(db, doc_id)
    can_edit, perm = _resolve_edit_permission(db, doc, x_owner_secret, share_token)
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
        is_owner=_is_owner(doc, x_owner_secret),
        permission=perm or ("edit" if _is_owner(doc, x_owner_secret) else None),
    )


@router.delete("/{doc_id}")
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    doc = get_doc_or_404(db, doc_id)
    require_owner(doc, x_owner_secret)
    doc.is_deleted = 1
    doc.updated_at = now_iso()
    # deactivate shares
    db.query(DocumentShare).filter(DocumentShare.doc_id == doc.id).update({"is_active": 0})
    db.commit()
    return {"ok": True}


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
    x_owner_secret: str | None = Header(default=None, alias="X-Owner-Secret"),
):
    doc = get_doc_or_404(db, doc_id)
    require_owner(doc, x_owner_secret)
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
