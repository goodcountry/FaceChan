import MarkdownIt from 'markdown-it'
import { greentextPlugin } from './plugins/greentext'
import { quoteLinkPlugin } from './plugins/quoteLink'

// External links (http/https) open in a new tab with noopener/noreferrer.
// Internal quote-links (#post-123) are excluded — those should navigate
// within the current page, not open a tab.
function addExternalLinkAttrs(md) {
  const defaultRender = md.renderer.rules.link_open || ((tokens, idx, options, env, self) =>
    self.renderToken(tokens, idx, options)
  )
  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    const href = token.attrGet('href') || ''
    if (/^https?:\/\//.test(href)) {
      token.attrSet('target', '_blank')
      token.attrSet('rel', 'noopener noreferrer')
    }
    return defaultRender(tokens, idx, options, env, self)
  }
}

// Markdown = On: full CommonMark (headers, lists, emphasis, code blocks,
// blockquote, hr, tables via lists/headers as discussed — no dedicated
// tables plugin) plus chan-style quote-links. `>` keeps its standard
// blockquote meaning here, so greentext is deliberately NOT enabled —
// see plugins/greentext.js for why.
export const mdFull = new MarkdownIt('default', {
  html: false,
  linkify: true,
  breaks: true,
}).use(quoteLinkPlugin)
addExternalLinkAttrs(mdFull)

// Markdown = Off: near-nothing, built up from the 'zero' preset. Only
// line breaks/paragraphs, greentext, and quote-links — no bold, no
// headers, no lists. Anything else in the text renders as literal
// characters.
export const mdMinimal = new MarkdownIt('zero', {
  html: false,
  linkify: true,
  breaks: true,
})
  .enable(['newline', 'paragraph', 'text', 'linkify'])
  .use(greentextPlugin)
  .use(quoteLinkPlugin)
addExternalLinkAttrs(mdMinimal)

/**
 * Render post/thread body text to sanitized HTML.
 * @param {string} text
 * @param {boolean} markdownEnabled - board's markdown_enabled flag (full vs minimal mode)
 * @returns {string} rendered HTML string (caller is responsible for DOMPurify.sanitize)
 */
export function renderMarkdown(text, markdownEnabled) {
  const md = markdownEnabled ? mdFull : mdMinimal
  return md.render(text)
}
