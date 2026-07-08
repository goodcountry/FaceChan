# FaceChan Roadmap

Features and tweaks planned, roughly in priority order. Nothing here is a promise — this is a living document.

PRs welcome on any of these.

---

## 🔴 High Priority

_Nothing currently blocking release._

---

## 🟡 Medium Priority

### Proper markdown parser
The current renderer (`utils/markdown.js`, `MarkdownBody.jsx`) is a hand-rolled regex pipeline — chosen originally to avoid an external dependency. It works for the common cases but regex-based parsing is fundamentally brittle for anything with nested or multi-line structure: list grouping in particular relies on detecting blank lines between items, and edge cases (e.g. a "blank" line that actually contains stray whitespace from pasted content) can silently break the grouping, which showed up as a real bug where every numbered list item rendered as "1." instead of incrementing. A proper tokenizing parser (e.g. `marked`, `markdown-it`, or a small custom AST-based implementation) would handle these structural cases correctly by construction instead of needing point patches for each newly discovered edge case. Worth revisiting once the dependency-free constraint is reassessed — trade-off is bundle size vs. correctness/maintainability.

### Content scraping protection
Two complementary layers — both off by default, operator-configurable per board:
- **Text obfuscation** — break up text strings programmatically before they reach the DOM; options include rendering text via custom fonts with scrambled Unicode mappings, or injecting zero-width spaces (`&#8203;`) dynamically between characters so copy-paste produces garbled output. Targets bulk scrapers and automated archiving tools.
- **Selection disable** — CSS `user-select: none` combined with React event listeners blocking copy/drag on sensitive threads. Per-board toggle in board settings.

### Mesh networking transport (offline/blackout mode)
Explore Bluetooth or Wi-Fi Direct ad-hoc syncing as a transport layer for situations where the internet is entirely blacked out — censorship, infrastructure failure, or deliberate isolation. FaceChan's ActivityPub federation model maps reasonably well onto store-and-forward delivery; posts could sync hop-by-hop across nearby devices with no internet required. Research phase only — protocol candidates include Meshtastic, BATMAN-adv, and Briar's transport layer.



### Internationalisation (i18n)

FaceChan is built for a global audience. UI translation is on the roadmap.

**Current state:** The codebase is English-only. Tech-savvy operators can edit strings directly. `LANGUAGES.md` in the repo root signals intent and welcomes community translation contributions.

**Planned work:**
- Django i18n middleware (`USE_I18N=True`, `LocaleMiddleware`)
- Extract all frontend strings into `i18next` translation files (`en.json` as the base)
- Language detection from browser `Accept-Language` header with user override
- Contributed translation files live under `frontend/src/locales/`
- No auto-translation — human-contributed only

**Not in scope for v1.** PRs with translation files for additional languages are welcomed ahead of the implementation being complete — they will be merged and held ready.

---

### Board subscriptions and personalised board view

Users can subscribe to specific boards, creating a personal "My Boards" view that shows only their chosen boards. The full board list remains accessible at all times to discover new boards and add them to the subscription.

**Design notes:**
- `BoardSubscription` model — user FK + board FK, unique together
- Subscriptions stored per user; no operator involvement needed
- Board list page gains a toggle: **All Boards** / **My Boards**; defaults to My Boards if the user has any subscriptions; falls back to All Boards if none set
- Subscribe/unsubscribe button on each board card and on the board header
- Feed view — if a user has subscriptions, the feed shows threads only from subscribed boards; if no subscriptions, current behaviour (all boards) is preserved
- Anonymous users always see all boards

### Content filtering and blocking

Per-user client-side and server-side filtering to reduce unwanted content. Privacy-preserving — filters are stored server-side against the user account but never shared or inspected by operators.

**What should be blockable:**
- **By board** — hide all threads from a specific board (equivalent to unsubscribing, but for boards you don't want to see even in the full list)
- **By display name** — hide all posts and threads from a specific display name; since display names aren't unique this is fuzzy, but sufficient for most cases; stable username blocking is a stricter alternative for known accounts
- **By keyword/phrase** — hide threads where the title or body matches a keyword or phrase; case-insensitive substring match; optional regex for power users
- **Subject line filter** — same as keyword but title-only; lower false positive rate

**Design notes:**
- `UserFilter` model — user FK, filter type (board/display_name/keyword/title_keyword), value string, created_at
- Filters applied at API level on thread list and feed endpoints — filtered threads simply don't appear, no indication to the filtered user that content exists
- Frontend filter management page at `/settings/filters` or as a section of the profile page
- No limit on number of filters per user (within reason — 500 cap prevents abuse)
- Filters apply to federated content too — a keyword filter works regardless of which instance a thread originated from

### Mixed clearnet/onion federation testing

Onion-to-onion federation is proven working. Clearnet-to-clearnet is untested but should work. **Clearnet-to-onion and onion-to-clearnet mixed-mode federation is untested** — the transport routing logic exists and should handle it, but HTTP signature verification across the mixed round-trip is an unknown. Needs a real test between a Railway/VPS clearnet instance and a Tor hidden service instance. See DEPLOYMENT.md for the full picture of what's known and unknown.

### Search enhancements
Current search is board-scoped thread search (title + body). Future: full-text search across posts within a thread, and optionally a global search across boards.

### Community enhancements
- Community banner image upload (on hold — not needed to ship)

---

## 🟢 Lower Priority / Nice to Have

### Lightning Network donations
BTC and Monero addresses are in `DONATE.md`. Lightning needs a static address — options are Wallet of Satoshi (no KYC, custodial) or self-hosted LNbits/BTCPay Server. Deferred until server infrastructure is in place.

### Analytics (privacy-preserving)
Self-hosted Plausible or Umami — no cookies, no fingerprinting, Tor-compatible.

### Onion-specific hardening
- No-JS fallback view for Tor Browser users with JS disabled

### Mod tools
- Standalone user search for staff — deliberately skipped for now. Community feedback will decide. The report queue already surfaces usernames. An open search-by-username endpoint raises privacy questions that cut against the anonymous-first ethos.

---

## ✅ Done

- **Fixed: plain-text posts collapsing line breaks** — `.fb-body` had no `white-space` rule, so the browser's default `white-space: normal` collapsed every newline in stored post text into a single run-on paragraph whenever markdown was disabled (the raw text in the DB was never actually mangled — this was purely a rendering issue). Added `white-space: pre-wrap` (plus `overflow-wrap: break-word` to guard against long unbroken strings) so single/double newlines render as the user typed them — one line break, or one blank-line paragraph gap — with no risk of a wall of blank lines since spacing is capped to exactly what's in the text, no arbitrary paragraph margin added on top
- **Enlarged reply composer textarea** — `.reply-composer textarea` (used when replying within a thread) was pinned to `rows={2}` / `min-height: 60px` with `resize: none`, making it hard to track your place past a line or two and impossible to resize manually. Bumped default to `rows={4}` / `min-height: 110px` and switched to `resize: vertical`, matching the new-thread composer's existing behaviour
- **Federated author display names + "Federated" badge** — federation stub users (`is_remote=True`) now save the remote actor's `name` field as `display_name` at creation time instead of discarding it, so federated replies show the poster's chosen display name instead of their raw `username@domain` handle (`UserSerializer`/`UserLink` already preferred `display_name` when present — it just wasn't being populated); `backfill_remote_display_names` management command re-fetches and backfills `display_name` for stub users created before this fix; `UserSerializer` now also exposes `is_remote`, and a small `⇄ Federated` pill (`FederatedBadge.jsx`, styled to match the founder/mod/PRO badge conventions) renders next to the author name on the OP header, single-post view, reply list, and board index cards whenever `author.is_remote` is true
- **Fixed: anonymous federated posts misattributed to the board's Group actor** — `build_thread_note`/`build_reply_note` attribute anonymous content to the board's own Group actor (with a `facechan:anonymous` flag) rather than a Person, since there's no author to attach to; inbound handling never checked that flag, so it treated the board's Group actor as if it were the post's author, creating a stub "Person" user whose display name was literally the remote board's name. `handle_create_note`/`handle_create_reply` now check `facechan:anonymous` and set `author=None` instead of resolving a stub user; `_get_or_create_stub_user` additionally refuses to create a stub from any fetched actor whose `type` isn't `Person`, as defense-in-depth against non-FaceChan senders that don't set the flag. `fix_misattributed_board_authors` management command cleans up stub users already created this way (deleting them restores the affected posts to anonymous via the `author` FK's `SET_NULL`)
- **Fixed: a user's first federated post losing author attribution** — `build_thread_note`/`build_reply_note` decided whether to include the author's Person actor in `attributedTo` via `hasattr(author, 'ap_actor')`, but a user's `Actor` row is only created lazily, the first time some remote server fetches `/ap/users/<username>` (`UserActorView`) — incidental to whether *this* post should be attributed to them. A logged-in user's very first federated post, before anyone had fetched their actor document, silently fell back to attributing the board alone, with no `facechan:anonymous` flag either (since `post.author` was still truthy) — indistinguishable on the receiving end from a genuinely anonymous post. Fixed by `get_or_create`-ing the `Actor` row at Note-build time instead of relying on incidental prior fetch order
- **Private messages (conversations)** — group-capable DMs between members, reusing `Thread`/`Post` (hidden `_dm` system board, `Thread.is_private_message` + `participants` M2M) rather than a separate model, so DMs inherit post/reply mechanics, CSAM hashing, and the report/quarantine pipeline for free; `ConversationViewSet` (`/api/conversations/`) for create/list/retrieve/leave/add-participant/remove-participant, sending replies reuses the ordinary thread-posts endpoint under a participant gate; `SiteSettings.enable_private_messages` kill switch; `private_message_staff_access_enabled` — OFF by default, admin-tier only, requires a written reason, audit-stamped who/when — a narrow override for e.g. a law-enforcement request, deliberately separate from ordinary board-scoped mod authority; `private_message_retention_days` auto-prune (mirrors `community_prune_days`, 0 = disabled)
- **Relay federation** — `SiteSettings.relay_federation_enabled` (off by default) + `max_relay_hops` (default 5); a thread/reply received from one federated instance can be re-forwarded to this instance's own followers, building a chain (1→2→3) rather than requiring every instance to follow every other instance directly; `Thread`/`Post` gain `relay_hop_count` and `relay_seen_instances` (JSON list of instance domains already in the chain, origin first); `relay_create_thread`/`relay_create_reply` Celery tasks preserve the ORIGINAL Note id and author across every hop (never regenerated from the local stub copy) and skip delivery to any follower already in the seen-instances chain; loop prevention is two-layer (seen-instances precise check + hop-count blunt backstop); `FederationActivity.is_relay` distinguishes relay from origin deliveries in the audit log
- **Fixed: duplicate federation delivery** — `core/signals.py` and `federation/signals.py` both had a `post_save` receiver for `Thread`, and the one in `core/signals.py` had no `is_remote` guard, so every inbound federated thread was re-broadcast outward again under the receiving instance's own identity. In a multi-instance federation mesh this caused the same post to arrive at a third instance twice via two different paths, under two different (regenerated, not preserved) Note ids — the existing `remote_ap_id` dedup check never caught the second arrival because the id itself had changed. Removed the duplicate, unguarded call entirely; `federation/signals.py`'s correctly-guarded receiver was already the right implementation
- **Auto-watch on thread create/reply** — creating a thread or replying to one now auto-adds it to the poster's watch list (`WatchedThread`); the full notification pipeline (FeedItem fan-out, WebSocket push, unread-count bell badge) already existed but was never populated since nothing created the initial watch
- **Persistent age verification** — `User.age_verified`, set via `POST /api/me/age-confirm/`, persists NSFW-board age confirmation on the account itself rather than only in browser `localStorage`; logged-in users now carry their confirmation across devices/browsers; logged-out/anonymous flow is unchanged (still localStorage + `X-Age-Verified` header, resets each fresh session, per COMPLIANCE.md design)
- **Site pages** — `SitePage` model (slug, title, markdown content, published, show_in_footer, display_order); Rules and FAQ seeded automatically; `can_manage_pages` role flag; **Mod → Pages** frontend editor with live preview; `GET /api/pages/` and `GET /api/pages/:slug/` public endpoints; `PATCH /api/pages/:slug/edit/` staff endpoint; pages linked automatically in site footer
- **Site footer** — dynamic footer links to published pages; Transparency link; MIT licence line; scroll-to-footer `↓` button in navbar next to theme toggle
- **Autocomplete fixes** — correct `autoComplete` attributes on login, register, and profile inputs; prevents browser autofilling strapline into username field
- **Avatar uploads** — operator toggle (`allow_avatars`, default off); `max_avatar_size_kb` cap (default 512KB); EXIF strip + square crop; CSAM checkpoint; camera icon overlay on profile
- **Markdown rendering** — regex-based parser (no external dependency); bold, italic, headings, blockquotes (accent-coloured left border), code blocks, links, lists, HR; operator toggle (`allow_markdown`, default on); thread card preview strips markdown to plain text; `utils/markdown.js` shared utility
- **Post editing** — `allow_post_editing` toggle (default off); `post_edit_window_seconds` (default 90, 0 = unlimited); live countdown timer in edit UI, restarts on keystroke; `edited_at` + `edit_count` fields on `Post`; "edited" badge shown on modified posts; staff follow same rules as everyone else
- **Login name vs display name** — `username` is stable private login credential; `display_name` shown everywhere (default = username at registration); duplicate display names allowed; `DisplayNameChangeLog` audit trail; 14-day cooldown; AP Actor `name` field uses display name, `preferredUsername` uses stable username
- **Bot protection** — honeypot `website` field on registration, thread creation, and reply forms (silent 200 on trigger); optional self-hosted mCaptcha via `MCAPTCHA_URL` + `MCAPTCHA_SITE_KEY` env vars (Tor-compatible, no third parties)
- **Communities toggle** — `enable_communities` in SiteSettings; hides nav link, returns 403 on creation; existing communities unaffected; enables blog-style single-operator deployments
- **Solarized light mode** — `[data-theme="light"]` CSS variable overrides; sun/moon toggle in navbar; preference persisted to `localStorage`; `prefers-color-scheme` respected as default; no flash on load via inline `<script>` in `index.html`
- **Outbound follow-state tracking** — `RemoteBoardMapping.follow_accepted` (nullable bool); set to `False` when Follow is queued, `True` when Accept arrives; federation dashboard shows ✓ Following / ⏳ Pending badge per board mapping
- **Reply federation live** — verified end-to-end: replies on remote threads deliver via `inReplyTo`, filed under the correct local thread, appear without refresh
- **Instance directory** — `INSTANCES.md` in the repo; operator self-submission via PR; content policy flags, federation status; disclaimer that Kino doesn't endorse any listed instance
- **Auto-create prune periodic task** — data migration creates the Celery Beat task on first run; no manual admin step needed
- **Mobile UX** — board header actions wrap to second row on small screens; compact reaction bar (active reactions + tap-to-open picker); NSFW boards hidden from board list for logged-out/unverified users
- **Profile editing** — strapline and bio editable from profile page; avatar shown on posts and replies; tagline shown below author name on posts
- **Password change** — `POST /api/me/password/` validates current password, reissues token; UI on profile page
- **Scroll to new post** — after replying to a thread OP, page smooth-scrolls to the new post
- **Seed boards** — 11 boards with readable slugs and 25 hand-written thread titles each; `/random` marked NSFW by default; no founder account in seed data
- Django REST Framework backend — boards, threads, posts, communities, reactions, feed
- React 18 + Vite frontend
- Token-based authentication (register, login)
- Community roles (member, mod, admin) with full join/leave/role management
- Sage posting, post quoting/threading, emoji reactions
- Personalised feed (community-weighted, private community gating)
- `SiteSettings` singleton — full admin control with no code changes
- User badges (`display_badge`: founder/mod/premium), tagline field
- Image uploads — WebP conversion, EXIF stripping, 2048px resize
- Docker Compose dev stack (single command, auto-seed on fresh DB)
- Docker Compose prod stack (Daphne + Postgres + Redis + Celery + Nginx + Tor)
- Dev compose healthcheck — nginx waits for Django to be healthy before accepting connections
- Nginx lazy DNS resolution, CSRF trusted origins, `.env.example`
- Django admin fully configured for all models
- **Compliance-by-design** — jurisdiction mode, content reporting, age confirmation, NSFW age-gating, transparency page, moderation contact; all on by default
- **Moderation system** — data-driven `Role` capability flags; board-scoped staff; ban/suspend revokes tokens immediately; three-tier content removal (hide → quarantine → purge)
- **Staff frontend** — `/mod` (report queue), `/mod/quarantine`, `/mod/users`; card and MUI DataGrid views (lazy-loaded)
- **Report audit survives purge** — `Report` snapshots author, board, content, preview, and poster IP at filing time
- **IP logging** — `poster_ip` on every thread and post; snapshotted into `Report.target_poster_ip`; admin-only
- **Thread pruning** — oldest non-pinned thread culled when board hits `max_threads_per_board`
- **Post/thread rate limits** — rolling 24h window, 0 = unlimited
- **Registration enforcement** — `SiteSettings.registration_open` toggle
- **Per-board image toggle** — `Board.allow_images`; text-only boards enforced at API and UI
- **Per-user media grant** — `User.can_post_media`; operator-only Django admin toggle; allows a specific user to attach images and videos when uploads are globally disabled; attach buttons hidden in UI for users without the grant
- **Username change audit + cooldown**
- **CSAM detection scaffolding** — mandatory checkpoint on images and video first frames, no off switch; pHash stored unconditionally; honest stub with full operator checklist
- **COMPLIANCE.md** — operator-responsibility doc, universal floor vs jurisdictional layer, three-tier content removal, IP logging data protection note
- **docs/risk-assessment-template.md**
- **Thread pinning** — `Role.can_pin_threads`; community creators and admins can also pin; pin/unpin on thread card and detail
- **Comments disabled** — `Thread.comments_disabled`; auto on pin, auto off on unpin; independently toggleable to cool any thread
- **Community discovery page** — sort by Trending/Active/Popular/Newest; search; activity labels; login redirect with return path
- **Community invite links** — tokenised URLs with optional expiry and max-uses; admin/mod management panel; public landing page; use count tracked; revocable
- **Login redirect** — `/login` reads `location.state.from` and returns after auth
- **Celery + Redis** — task queue and beat scheduler; `django-celery-beat` for DB-driven schedules in Django admin
- **Community pruning** — `SiteSettings.community_prune_days`; Celery beat task; no exceptions; manual `prune_communities` command
- **Community activity annotations** — `active_posts` (48h) and `trending_posts` (24h) on community list API
- **Activity tiers** — operator-configurable; defaults Lurker → Regular → Veteran → Prolific Poster → Legend
- **Thumbnail generation** — 320×180px WebP, centre-cropped 16:9
- **Catalog view** — OP thumbnail grid, toggle persisted to localStorage
- **Watch thread** — bell notifications; Watched tab on Feed with per-thread unread counts
- **Bump lock** — `SiteSettings.bump_lock_percent` (default 75, max 95); sage never bumps
- **PWA** — `vite-plugin-pwa` + Workbox; web app manifest; standalone display; 192/512 icons + Apple touch icon; API calls NetworkOnly; SW and manifest no-cache from nginx; installs to home screen on Android and iOS
- **Responsive navbar** — icons-only on mobile (≤600px); full labels on desktop
- **Board-scoped thread search** — `?search=` on `/api/threads/?board=` filters title and body; debounced search input in board header with result count and clear button
- **Duck Roll word filter** — `WordFilter` model; site-wide and per-board scope; plain substring or regex; applied at read time in serializers; raw text always preserved in DB; per-process cache with admin-triggered invalidation; fully managed in Django admin
- **WebSocket real-time notifications** — Django Channels + Redis channel layer; `NotificationConsumer` per user (`notifications_{user_id}` group); pushed instantly on post create; `NotificationContext` uses WebSocket primary with automatic 60s poll fallback; Daphne replaces Gunicorn as ASGI server; nginx `/ws/` proxy with 24h keepalive
- **Video uploads** — MP4 and WebM; FFmpeg re-encode strips all metadata; duration cap (default 5 min); size cap (default 50MB); thumbnail from first frame; CSAM pHash on first frame; `Board.allow_videos` and `Board.allow_video_sound` per-board toggles; cascade-off rules enforced at model layer (`allow_images=False` forces both off; `allow_videos=False` forces sound off); `VideoPlayer` component with compact thumbnail mode, hover-to-autoplay, lazy loading
- **Emergency procedures** — documented shutdown and key destruction steps in `DEPLOYMENT_ONION.md`; covers container teardown, Tor key destruction, log purging, and the limits of software-only wiping on SSDs
- **DEPLOYMENT.md** — full security hardening guide: LUKS full-disk encryption, VeraCrypt hidden volumes, Tor hardening, firewall rules, SSH hardening, OpSec, data minimisation, legal compulsion guidance, operator checklist
- **Onion discoverability guide** — Ahmia, Torch, Haystak, DarkSearch, The Hidden Wiki, r/onions; safe promotion via Tor-only; timing discipline; throwaway accounts; promotion checklist added to DEPLOYMENT.md
- **DONATE.md** — Monero (XMR) and Bitcoin (BTC) addresses with QR codes; Lightning placeholder
- **Federation Phase 3 — reply federation** — `Post` gains `is_remote`, `remote_ap_id`, `remote_actor_url` fields; `build_reply_note()` builds a `Note` with `inReplyTo`; `deliver_create_reply` Celery task delivers to thread origin board inbox and all followers; inbound handler routes on `inReplyTo` presence, deduplicates, reconciles parent thread by `remote_ap_id` or local UUID, stores as `Post` with stub author
- **Federation Phase 4 — board WebSocket listener** — `BoardDetail.jsx` opens `ws(s)://host/ws/boards/<slug>/` on mount; prepends incoming `new_thread` events to the thread list without a page refresh; deduplication prevents double-display; cleanup on unmount
- **Federation Phase 6 — Tor SOCKS outbound** — per-URL transport routing in `fetch.py` (`_client_for`): `.onion` destinations route through a dedicated outbound Tor container (`tor-proxy`, `dperson/torproxy`) via `socks5h://tor-proxy:9050`, clearnet goes direct; `FEDERATION_SOCKS_PROXY` setting; `socksio` dependency; longer timeout for onion circuits; `fetch_instance_boards` task implemented (was referenced but missing); wired into dev test stack and prod compose
- **Federation — outbound Follow on mapping** — mapping a remote board to a local board sends a `Follow` to the remote board actor (`build_follow_activity`, `deliver_follow` task), so the remote instance begins delivering that board's threads to us; fires on both mapping create and update; remote side auto-accepts via `_handle_follow`; inbound `Accept` is logged as a no-op (outbound follow-state tracking deferred). This is the piece that makes content actually flow after discovery + mapping
- **Federation foundation** — `federation` Django app; Actor/RemoteInstance/RemoteActor/Follow/FederationActivity models; HTTP Signatures; Webfinger; Board Actor/Inbox/Outbox/Followers + User Actor endpoints; `deliver_accept` + `deliver_create_thread` Celery tasks; post_save signal wiring; anonymous threads stay local; `FEDERATION_BASE_URL` env var
- **Federation inbound** — `Create(Note)` handler; `RemoteBoardMapping` (operator maps remote slug → local board); stub User accounts for remote authors (`is_remote=True`); `Thread.is_remote` + `remote_ap_id` deduplication; HTML stripping; `BoardConsumer` WebSocket push on inbound thread
- **Federation dashboard** — `RemoteBoard` cache model; `/ap/instance` public discovery endpoint; `fetch_instance_boards` Celery task (auto-triggered on instance approval); `Board.allow_federation` per-board flag; `SiteSettings.federation_enabled` master switch; full federation management API (admin-only); `FederationDashboard.jsx` at `/mod/federation` — master switch, instance cards, board mapping dropdowns, local board list; Globe nav item in mod sidebar
- **DEPLOYMENT.md federation section** — clearnet/onion/dual-stack scenarios; `FEDERATION_BASE_URL` explained; instance allowlist workflow; what federates vs stays local; .onion key as federation identity; legal exposure from federated content; instance directory placeholder
