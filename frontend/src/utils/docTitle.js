/** 用正文第一条有字的行作为文档标题。 */
export function titleFromContent(content) {
  const line = String(content || '')
    .split(/\r?\n/)
    .map((row) => row.trim())
    .find((row) => row)
  if (!line) return '无标题文档'
  return line.replace(/^#+\s*/, '') || '无标题文档'
}
