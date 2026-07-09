import { useMemo } from 'react'
import DOMPurify from 'dompurify'
import { useSiteSettings } from '../context/SiteSettingsContext'
import { renderMarkdown } from '../lib/markdown'

/**
 * @param {string} text
 * @param {string} className
 * @param {boolean} [markdownEnabled] - board's markdown_enabled flag. When
 *   provided, selects full markdown-it (true) vs minimal greentext-only
 *   mode (false) for boards. When omitted (private messages, site pages,
 *   mod previews — contexts with no board), falls back to full markdown
 *   whenever the site-wide allow_markdown setting is on, matching prior
 *   sitewide behaviour for those surfaces.
 */
export default function MarkdownBody({ text, className = 'fb-body markdown-body', markdownEnabled }) {
  const settings = useSiteSettings()
  const allow_markdown = settings?.allow_markdown

  const html = useMemo(() => {
    if (!text) return ''
    if (allow_markdown === false) return ''
    try {
      const useFullMarkdown = markdownEnabled !== undefined ? markdownEnabled : true
      const rendered = renderMarkdown(text, useFullMarkdown)
      // DOMPurify strips target="_blank" by default even with rel set;
      // explicitly allow it since addExternalLinkAttrs() relies on it
      // and always pairs it with rel="noopener noreferrer".
      return DOMPurify.sanitize(rendered, { ADD_ATTR: ['target'] })
    } catch (e) {
      return ''
    }
  }, [text, allow_markdown, markdownEnabled])

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
