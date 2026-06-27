"""
Duck Roll — word filter utility.

Filters are applied at read time (in serializers), never on write.
Raw text is always preserved in the DB — filters can be updated or
removed and old content immediately reflects the change.

A simple per-process cache avoids repeated DB hits when serializing
many posts. The cache is invalidated by calling bust_cache(), which
is called automatically by WordFilterAdmin on save/delete.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Module-level cache: { board_slug_or_None: [(compiled_pattern, replacement), ...] }
_cache: dict = {}
_cache_ready = False


def bust_cache():
    """Call this whenever WordFilter rows change (save/delete signal or admin action)."""
    global _cache, _cache_ready
    _cache = {}
    _cache_ready = False


def _load_filters():
    """Load all active filters into the cache. Called once per process lifetime (or after bust)."""
    global _cache, _cache_ready
    if _cache_ready:
        return

    from .models import WordFilter
    _cache = {}

    for wf in WordFilter.objects.filter(is_active=True).select_related('board'):
        board_slug = wf.board.slug if wf.board and wf.scope == 'board' else None

        try:
            if wf.is_regex:
                compiled = re.compile(wf.pattern, re.IGNORECASE)
            else:
                compiled = re.compile(re.escape(wf.pattern), re.IGNORECASE)
        except re.error:
            logger.warning('WordFilter %s has invalid regex pattern "%s" — skipped.', wf.pk, wf.pattern)
            continue

        # None key = site-wide; board slug key = board-specific
        _cache.setdefault(None, [])
        if board_slug:
            _cache.setdefault(board_slug, [])
            _cache[board_slug].append((compiled, wf.replacement))
        else:
            _cache[None].append((compiled, wf.replacement))

    _cache_ready = True


def apply_word_filters(text: str, board_slug: str | None = None) -> str:
    """
    Apply active word filters to text and return the result.

    Applies site-wide filters first, then board-specific ones (if board_slug given).
    Safe to call with None board_slug — only site-wide filters apply.
    """
    if not text:
        return text

    _load_filters()

    # Site-wide filters
    for pattern, replacement in _cache.get(None, []):
        text = pattern.sub(replacement, text)

    # Board-specific filters
    if board_slug:
        for pattern, replacement in _cache.get(board_slug, []):
            text = pattern.sub(replacement, text)

    return text
