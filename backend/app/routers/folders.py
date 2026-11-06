"""当前登录账号的文件夹。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Document, DocumentShare, Folder, UserDoc
from app.routers.admin_auth import require_user_id
from app.schemas import FolderCreate, FolderDeleteOut, FolderOut, FolderPinIn, FolderRename
from app.utils import now_iso

router = APIRouter(prefix="/api/folder", tags=["folder"])


def _own_folder(db: Session, user_id: int, folder_id: int) -> Folder:
    """取出当前账号的文件夹，不是自己的则拒绝。"""
    row = (
        db.query(Folder)
        .filter(Folder.id == folder_id, Folder.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    return row


def _to_out(row: Folder) -> FolderOut:
    """把文件夹行转成接口输出。"""
    return FolderOut(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        pinned=bool(row.pinned_at),
    )


@router.get("", response_model=list[FolderOut])
def list_folders(user_id: int = Depends(require_user_id), db: Session = Depends(get_db)):
    """列出当前账号的文件夹，已置顶的排在前面。"""
    rows = (
        db.query(Folder)
        .filter(Folder.user_id == user_id)
        .order_by(
            case((Folder.pinned_at.is_not(None), 0), else_=1),
            Folder.pinned_at.desc(),
            Folder.id.asc(),
        )
        .all()
    )
    return [_to_out(r) for r in rows]


@router.post("", response_model=FolderOut)
def create_folder(
    body: FolderCreate,
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """为当前账号新建一个文件夹。"""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")
    row = Folder(user_id=user_id, name=name, created_at=now_iso())
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.put("/{folder_id}", response_model=FolderOut)
def rename_folder(
    folder_id: int,
    body: FolderRename,
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """重命名当前账号的文件夹。"""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")
    row = _own_folder(db, user_id, folder_id)
    row.name = name
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/{folder_id}/pin", response_model=FolderOut)
def pin_folder(
    folder_id: int,
    body: FolderPinIn,
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """置顶或取消置顶当前账号的文件夹。"""
    row = _own_folder(db, user_id, folder_id)
    row.pinned_at = now_iso() if body.pinned else None
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{folder_id}", response_model=FolderDeleteOut)
def delete_folder(
    folder_id: int,
    user_id: int = Depends(require_user_id),
    db: Session = Depends(get_db),
):
    """删除文件夹：自己的文档软删除；收到的文档退回「收到的」，不删原文。"""
    row = _own_folder(db, user_id, folder_id)
    docs = (
        db.query(Document)
        .filter(
            Document.folder_id == row.id,
            Document.is_deleted == 0,
            (Document.user_id == user_id) | (Document.user_id.is_(None)),
        )
        .all()
    )
    doc_ids = [d.id for d in docs]
    ts = now_iso()
    for doc in docs:
        doc.is_deleted = 1
        doc.updated_at = ts
    if doc_ids:
        (
            db.query(DocumentShare)
            .filter(DocumentShare.doc_id.in_(doc_ids))
            .update({"is_active": 0}, synchronize_session=False)
        )
    # 中文：归在这个文件夹里的收到文档只清掉归类，原文留在创建者那里
    db.query(UserDoc).filter(
        UserDoc.user_id == user_id, UserDoc.folder_id == row.id
    ).update({"folder_id": None, "updated_at": ts}, synchronize_session=False)
    db.delete(row)
    db.commit()
    return FolderDeleteOut(ok=True, doc_ids=doc_ids)
