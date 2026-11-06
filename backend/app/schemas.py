from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Permission = Literal["read", "comment", "edit"]
CommentStatus = Literal["pending", "resolved"]


class DocCreate(BaseModel):
    title: str = "无标题文档"
    content: str = ""
    folder_id: Optional[int] = None


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
    folder_id: Optional[int] = None
    comment_count: int = 0
    resolved_count: int = 0
    pending_comments: list[str] = []
    content_size: int = 0
    sub_lines: str = ""
    is_shared: bool = False
    # 最近活动过的未删除批注（按 updated_at），供列表「评论提交」列显示
    latest_comment_anon_name: Optional[str] = None
    latest_comment_at: Optional[str] = None

class MineDocItem(DocListItem):
    """首页「我的文档」条目：自己创建的或收到的分享。"""

    # owned 自己创建；received 别人分享给我
    origin: str = "owned"
    # 收到时，创建者的用户名
    from_name: Optional[str] = None


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
    folder_id: Optional[int] = None
    # 当前视角：owned 自己创建，received 收到的分享，None 无归属
    origin: Optional[str] = None
    # 收到时，创建者的用户名
    from_name: Optional[str] = None


class DocCreateOut(BaseModel):
    id: int
    owner_secret: str
    title: str
    content: str
    created_at: str
    updated_at: str


class DocBatchRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class DocSearchRequest(BaseModel):
    """在一批文档的标题、正文和批注里查找关键字。"""

    ids: list[int] = Field(default_factory=list)
    q: str = ""


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
    context_prefix: Optional[str] = None
    context_suffix: Optional[str] = None


class CommentUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[CommentStatus] = None
    anon_name: Optional[str] = None
    client_key: Optional[str] = None
    # 打开编辑框时看到的更新时间；对不上说明别人先改过
    expected_updated_at: Optional[str] = None


class CommentAnchorUpdate(BaseModel):
    """只更新批注在正文中的锚点，不改批注正文。"""
    offset_start: int
    offset_end: int
    selected_text: str
    context_prefix: Optional[str] = None
    context_suffix: Optional[str] = None


class CommentAnchorBatchItem(CommentAnchorUpdate):
    id: int


class CommentAnchorBatch(BaseModel):
    items: list[CommentAnchorBatchItem] = Field(default_factory=list)


class CommentOut(BaseModel):
    id: int
    doc_id: int
    parent_id: Optional[int]
    selected_text: str
    content: str
    offset_start: int
    offset_end: int
    context_prefix: Optional[str] = None
    context_suffix: Optional[str] = None
    status: CommentStatus
    anon_name: str
    created_at: str
    updated_at: str
    client_key: Optional[str] = None
    replies: list["CommentOut"] = Field(default_factory=list)


CommentOut.model_rebuild()


class AdminMeOut(BaseModel):
    """当前登录者。name 是顶栏展示名；login_path 仅登录后返回，供退出时回到登录页。"""

    ok: bool = True
    name: str = "管理员"
    login_path: str = ""


class AdminGateIn(BaseModel):
    """核对当前浏览器路径是否为配置中的登录入口。"""

    path: str


class AdminGateOut(BaseModel):
    """路径是否与 config.ini 的 login_path 完全一致（不回传真实路径）。"""

    ok: bool


class FolderCreate(BaseModel):
    """新建文件夹。"""

    name: str


class FolderRename(BaseModel):
    """重命名文件夹。"""

    name: str


class FolderPinIn(BaseModel):
    """是否置顶。"""

    pinned: bool


class FolderOut(BaseModel):
    """当前账号的一个文件夹。"""

    id: int
    name: str
    created_at: str
    pinned: bool = False


class FolderDeleteOut(BaseModel):
    """删除文件夹后，一并软删除的文档 id。"""

    ok: bool
    doc_ids: list[int] = Field(default_factory=list)


class DocMoveIn(BaseModel):
    """移动文档的目标文件夹。空表示未分类。"""

    folder_id: Optional[int] = None


class AuthRegisterIn(BaseModel):
    """公开注册：账号和明文密码（服务端哈希后存库）。"""

    username: str
    password: str


class AuthLoginIn(BaseModel):
    """统一登录：账号和明文密码；path 是当前浏览器路径，管理员登录必须与 ini login_path 一致。"""

    username: str
    password: str
    path: str = ""


class AuthTokenOut(BaseModel):
    """注册/登录成功返回的会话。"""

    token: str
    expires_in: int
    username: str


class ClaimLegacyItem(BaseModel):
    """本机持有密钥的一篇旧文档，用来绑定到当前账号。"""

    id: int
    owner_secret: str


class ClaimLegacyIn(BaseModel):
    """要绑定的旧文档清单。"""

    items: list[ClaimLegacyItem] = Field(default_factory=list)


class ClaimLegacyOut(BaseModel):
    """绑定结果：成功绑定的篇数。"""

    claimed: int = 0
