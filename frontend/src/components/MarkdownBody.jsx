import { useMemo } from 'react'
import { useSiteSettings } from '../context/SiteSettingsContext'

function parseMarkdown(text) {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Normalize lines that are visually blank but contain stray whitespace
  // (e.g. pasted content), so the list-collapsing regexes below can
  // detect them as blank lines. Without this, a "blank" line containing
  // a stray space breaks list grouping and every item renders as its
  // own single-item list (e.g. numbered items all showing "1.").
  html = html.split('\n').map(line => (line.trim() === '' ? '' : line)).join('\n')

  html = html.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    `<pre><code>${code.trim()}</code></pre>`
  )
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  html = html.replace(/^---$/gm, '<hr>')

  // Collapse blank lines between bullet list items then group into a single <ul>
  html = html.replace(/(- .+)\n\n+(?=- )/g, '$1\n')
  html = html.replace(/((- .+\n?)+)/g, match => {
    const items = match.trim().split('\n').map(line =>
      `<li>${line.replace(/^- /, '')}</li>`
    ).join('')
    return `<ul>${items}</ul>`
  })

  // Collapse blank lines between numbered list items then group into a single <ol>
  html = html.replace(/(\d+\. .+)\n\n+(?=\d+\. )/g, '$1\n')
  html = html.replace(/((\d+\. .+\n?)+)/g, match => {
    const items = match.trim().split('\n').map(line =>
      `<li>${line.replace(/^\d+\. /, '')}</li>`
    ).join('')
    return `<ol>${items}</ol>`
  })

  html = html.split(/\n\n+/).map(block => {
    block = block.trim()
    if (!block) return ''
    if (/^<(h[1-3]|ul|ol|pre|blockquote|hr)/.test(block)) return block
    return `<p>${block.replace(/\n/g, '<br>')}</p>`
  }).join('\n')

  return html
}

export default function MarkdownBody({ text, className = 'fb-body markdown-body' }) {
  const settings = useSiteSettings()
  const allow_markdown = settings?.allow_markdown

  const html = useMemo(() => {
    if (!text) return ''
    if (allow_markdown === false) return ''
    try {
      const result = parseMarkdown(text)
      return result
    } catch (e) {
      return ''
    }
  }, [text, allow_markdown])

  if (allow_markdown === false || !html) {
    return <p className="fb-body">{text}</p>
  }

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
