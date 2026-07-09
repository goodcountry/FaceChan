/**
 * Greentext plugin for markdown-it.
 *
 * Renders a line starting with a single `>` (not `>>`, which is reserved
 * for quote-links — see quoteLink.js) as its own green-text paragraph,
 * chan-style. e.g.
 *
 *   >implying markdown-it wasn't a good idea
 *
 * Deliberately scoped to Markdown = Off boards only. On Markdown = On
 * boards, `>` keeps its standard CommonMark meaning (blockquote), which
 * matters for recipe/document-style posts.
 *
 * Each matching line becomes its own paragraph (not merged into a single
 * multi-line block), matching the previous regex parser's per-line
 * behaviour.
 */
const GREENTEXT_RE = /^>(?!>)/

export function greentextPlugin(md) {
  md.block.ruler.before('paragraph', 'greentext', (state, startLine, endLine, silent) => {
    const start = state.bMarks[startLine] + state.tShift[startLine]
    const max = state.eMarks[startLine]
    const line = state.src.slice(start, max)

    if (!GREENTEXT_RE.test(line)) return false
    if (silent) return true

    const content = line.replace(/^>\s?/, '')

    const openToken = state.push('paragraph_open', 'p', 1)
    openToken.attrs = [['class', 'greentext']]
    openToken.map = [startLine, startLine + 1]

    const inlineToken = state.push('inline', '', 0)
    inlineToken.content = content
    inlineToken.map = [startLine, startLine + 1]
    inlineToken.children = []

    state.push('paragraph_close', 'p', -1)

    state.line = startLine + 1
    return true
  })
}
