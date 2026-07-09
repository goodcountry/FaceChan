/**
 * Quote-link plugin for markdown-it.
 *
 * Renders `>>123` as a link to `#post-123`, chan-style. Implemented as an
 * inline rule (not a block rule) so it fires anywhere in a line of text —
 * "agreed with >>123" — not just at line-start.
 *
 * Known gap: `>>123` written as the very first characters of a line on a
 * Markdown = On board will instead be consumed by CommonMark's blockquote
 * block rule (which runs before inline parsing), producing a nested empty
 * blockquote rather than a quote-link. Quote-links written inline, or
 * anywhere on a Markdown = Off board, are unaffected. Not worth resolving
 * with a custom block-level override for now — flagging it rather than
 * quietly leaving it.
 *
 * Also currently only reaches top-level posts: replies have UUID ids and
 * aren't assigned a visible post_number by the API, so there's nothing
 * for a `>>123` inside a reply's own number to resolve to yet.
 */
const QUOTE_LINK_RE = /^>>(\d+)/

export function quoteLinkPlugin(md) {
  md.inline.ruler.push('quote_link', (state, silent) => {
    const match = QUOTE_LINK_RE.exec(state.src.slice(state.pos))
    if (!match) return false

    if (!silent) {
      const postNumber = match[1]

      const openToken = state.push('quote_link_open', 'a', 1)
      openToken.attrs = [
        ['href', `#post-${postNumber}`],
        ['class', 'quote-link'],
        ['data-post-number', postNumber],
      ]

      const textToken = state.push('text', '', 0)
      textToken.content = `>>${postNumber}`

      state.push('quote_link_close', 'a', -1)
    }

    state.pos += match[0].length
    return true
  })
}
