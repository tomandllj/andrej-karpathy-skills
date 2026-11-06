/**
 * 中文：商务文稿极简双主题 — Tailwind theme.extend 参考片段。
 * 不接入构建；运行时色值来自 frontend/src/styles.css 的 CSS 变量。
 * 若日后引入 Tailwind，可：theme: { extend: require('./design-tokens/tailwind.extend.js') }
 */
module.exports = {
  colors: {
    page: 'var(--bg-page)',
    elevated: 'var(--bg-elevated)',
    muted: {
      DEFAULT: 'var(--bg-muted)',
      fg: 'var(--text-muted)',
    },
    accent: {
      DEFAULT: 'var(--accent)',
      soft: 'var(--accent-soft)',
      hover: 'var(--accent-hover)',
    },
    title: 'var(--text-title)',
    body: 'var(--text-body)',
    link: 'var(--text-link)',
    sidebar: {
      DEFAULT: 'var(--sidebar-bg)',
      border: 'var(--sidebar-border)',
    },
    code: {
      DEFAULT: 'var(--code-bg)',
      fg: 'var(--code-fg)',
      border: 'var(--code-border)',
      inline: 'var(--code-inline-bg)',
      'inline-fg': 'var(--code-inline-fg)',
    },
    toc: {
      DEFAULT: 'var(--toc-fg)',
      hover: 'var(--toc-fg-hover)',
      active: 'var(--toc-fg-active)',
    },
  },
  fontFamily: {
    sans: [
      '-apple-system',
      'BlinkMacSystemFont',
      'Segoe UI',
      'PingFang SC',
      'Microsoft YaHei',
      'sans-serif',
    ],
    mono: [
      'ui-monospace',
      'SF Mono',
      'JetBrains Mono',
      'Menlo',
      'Consolas',
      'monospace',
    ],
  },
  borderRadius: {
    sm: 'var(--radius-sm)',
    md: 'var(--radius-md)',
    lg: 'var(--radius-lg)',
    xl: 'var(--radius-xl)',
  },
}
