# 需求规格说明书｜Markdown在线批注协作平台（SQLite单文件版 · 无登录版）
> 变更说明：一期去掉用户登录体系，全部匿名访问；后期再扩展账号登录；数据库使用 SQLite 单文件 app.db
> 技术栈：Python FastAPI + SQLite + SQLAlchemy 2.0 + Vue3 + Element Plus + WebSocket
> 部署：前后端分开启；前端 Vite 开发服，后端 FastAPI；前端必须支持 Mermaid 流程图（mermaid.js 前端渲染）

## 核心目标
编写MD文档、生成共享链接、3档权限(read/comment/edit)、预览文本高亮标记批注、侧边批注面板、版本快照、Mermaid渲染；批注不修改正文。

## 角色
- 文档创建人：localStorage 存 owner_secret；可改正文、管理批注、分享、版本、导出、删除
- 协作者：分享链接权限；匿名昵称

## 数据库（无 user 表）
document, document_share, document_version, comment — 见完整规格

## API
文档/分享/批注 REST + ws://.../ws/doc/{doc_id} 推送 comment.new/update/delete
关键操作校验 X-Owner-Secret；comment/read 拒绝改正文

## 前端
首页列表 + 编辑页双栏 + 批注面板 + 分享弹窗；Mermaid；1.5s 防抖保存
一期不做：登录、分享过期、图片上传、PDF、多人正文协同、多层回复

完整细节以用户原始规格为准（本文件为摘要）。
