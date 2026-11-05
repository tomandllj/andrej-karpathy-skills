from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Permission = Literal["read", "comment", "edit"]
CommentStatus = Literal["pending", "resolved"]


class DocCreate(BaseModel):
    title: str = "无标题文档"
    content: str = ""


class DocUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    remark: Optional[str] = None


class DocListItem(BaseModel):
    id: int
    title: str
    updated_at: str
    created_at: str
    is_deleted: int


class DocOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str
    is_owner: bool = False
    permission: Optional[Permission] = None
    share_id: Optional[int] = None
    share_token: Optional[str] = None


class DocCreateOut(BaseModel):
    id: int
    owner_secret: str
    title: str
    content: str
    created_at: str
    updated_at: str


class DocBatchRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class ShareCreate(BaseModel):
    permission: Permission = "comment"


class ShareUpdate(BaseModel):
    permission: Optional[Permission] = None
    is_active: Optional[bool] = None


class ShareOut(BaseModel):
    id: int
    doc_id: int
    share_token: str
    permission: Permission
    is_active: int
    created_at: str
    share_url_path: str


class VersionOut(BaseModel):
    id: int
    doc_id: int
    version_no: int
    remark: Optional[str]
    created_at: str
    content_preview: Optional[str] = None


class VersionDetail(BaseModel):
    id: int
    doc_id: int
    version_no: int
    content_snapshot: str
    remark: Optional[str]
    created_at: str


class CommentCreate(BaseModel):
    selected_text: str
    content: str
    offset_start: int
    offset_end: int
    anon_name: str
    parent_id: Optional[int] = None
    client_key: Optional[str] = None  # front-end key to claim own comments


class CommentUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[CommentStatus] = None
    anon_name: Optional[str] = None
    client_key: Optional[str] = None


class CommentOut(BaseModel):
    id: int
    doc_id: int
    parent_id: Optional[int]
    selected_text: str
    content: str
    offset_start: int
    offset_end: int
    status: CommentStatus
    anon_name: str
    created_at: str
    updated_at: str
    client_key: Optional[str] = None
    replies: list["CommentOut"] = Field(default_factory=list)


CommentOut.model_rebuild()
