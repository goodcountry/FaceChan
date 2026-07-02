# FaceChan

> *"People want paradise — they shall have it. Terms and conditions apply."*

Self-hostable anonymous imageboard. Run your own instance over Tor or clearnet. No platform, no deplatforming, no advertisers, no data collection.

A fusion of anonymous board culture and social mechanics. Built to be owned by nobody and everyone. Federated by design — no single instance can be silenced.

MIT licensed. Fork it. Run it. Make it yours.

---

## What it is

- **Anonymous-first** imageboards — boards, threads, post numbers, sage, quoting
- **Facebook-style social layer** — communities, reactions, personalised feed
- **ActivityPub federation** — boards federate across instances; no central authority, no single point of failure
- **Federation dashboard** — admin UI to connect instances, discover remote boards, and map them to local boards with a dropdown — no typing slugs manually
- **Community discovery** — trending, active, newest sort modes; search by name/description
- **Community invite links** — tokenised links with optional expiry and max-uses for private communities
- **Board-scoped thread search** — search threads by title and body within any board
- **Image uploads** — WebP conversion, EXIF stripping, auto-resize; per-board image toggle for text-only boards; per-user media grant for when uploads are globally off
- **Video uploads** — short MP4/WebM clips; FFmpeg re-encode + metadata strip; per-board video and sound toggles; duration cap; thumbnail from first frame; CSAM checkpoint on first frame
- **Avatar uploads** — operator toggle; 512KB default cap; EXIF strip + square crop; CSAM checkpoint
- **Markdown rendering** — posts and thread OPs render bold, italic, headings, blockquotes, code, links, lists; operator toggle; thread card preview strips markdown to plain text
- **Hyperlink control** — per-board and global toggle to allow or disallow `http/https` URLs in thread titles, bodies, and replies; off by default; bare domain names always permitted; blocked at write time with a clear error
- **Site pages** — operator-authored Rules, FAQ, and custom pages in markdown; managed via Mod → Pages UI; links appear automatically in the site footer; `can_manage_pages` role flag controls who can edit
- **Site footer** — dynamic links to all published footer pages plus Transparency; scroll-to-footer button in navbar; MIT licence and no-tracking notice
- **Post editing** — operator toggle; configurable time window (default 90s); live countdown timer restarts on keystroke; edited badge on modified posts
- **Real-time notifications** — WebSocket push via Django Channels; bell updates instantly on new replies to watched threads; automatic fallback to 60s polling for Tor users or degraded connections
- **Real-time board updates** — federated threads pushed to board views instantly via board-scoped WebSocket channel
- **Thread pinning + comments control** — pin threads, disable/enable comments independently
- **Duck Roll word filter** — per-board and site-wide word/phrase substitution at read time; raw text always preserved
- **Automated community pruning** — inactive communities deleted on a schedule via Celery; periodic task created automatically on first migration run
- **Private messages** — group-capable conversations between members, reusing the same post/reply mechanics (and CSAM/report/quarantine pipeline) as everything else; operator kill switch; audited admin-only override for staff visibility (off by default); automated pruning of inactive conversations on the same schedule as communities
- **Bot protection** — honeypot field on all submission forms (silent reject); optional self-hosted mCaptcha (Tor-compatible, no third parties)
- **Login name vs display name** — `username` is the private stable login credential; `display_name` is shown publicly and changeable (with cooldown); duplicate display names allowed — everyone can be "anonymous"
- **Solarized light/dark mode** — per-user toggle in navbar; persists to `localStorage`; respects `prefers-color-scheme`; no flash on load
- **PWA** — installs to home screen on Android and iOS; standalone mode; no app store required
- **Responsive** — works on mobile, tablet, and desktop; header actions wrap on mobile; compact reaction bar on small screens
- **Two deployment targets** — clearnet (Railway/VPS) and Tor hidden service (.onion)
- **Emergency procedures** — documented shutdown and key destruction steps for operators in high-risk environments; see `DEPLOYMENT_ONION.md`
- **Self-hostable** — clone, run Docker, own your instance
- **Configurable** — everything controlled from Django admin; no code changes needed for day-to-day operation

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Django 5.2 + Django REST Framework |
| Frontend | React 18 + Vite + vite-plugin-pwa (MUI DataGrid for `/mod` only, lazy-loaded) |
| Database | PostgreSQL |
| Task queue | Celery 5 + Redis 7 |
| Server | Daphne (ASGI) + Nginx |
| Containers | Docker + Docker Compose |
| Onion | Tor v3 hidden service |
| Media | Local disk (default) or Cloudflare R2 (clearnet) |
| Federation | ActivityPub (W3C standard) + HTTP Signatures |

---

## Quick Start — Local Dev

```bash
git clone https://github.com/goodcountry/FaceChan.git
cd FaceChan
docker compose up --build -d
```

Everything starts together. On a fresh database the seed command runs automatically and creates 11 boards with 25 threads each.

| Service | URL |
|---|---|
| Site | http://localhost |
| API | http://localhost/api/ |
| Django admin | http://localhost/admin |

**Create your admin account:**
```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py grant_admin <username>
```

---

## First-time Setup

### 1. Configure site settings

**Admin → Site Settings:**

- **Site name / tagline**
- **Board, thread, post and community limits**
- **Bump lock percent** (default 75, max 95)
- **Community prune days** (default 30, 0 = disabled)
- **Registration** open/closed
- **Enable communities** — hide the communities feature entirely for blog-style deployments
- **NSFW** board toggle — NSFW boards are hidden from all logged-out users; login and age confirmation both required to see or access them
- **Image / video upload** limits
- **Allow avatars** — off by default; `max_avatar_size_kb` caps upload size (default 512KB)
- **Per-user media grant** — `User.can_post_media`; operator-only toggle in Django admin; lets a specific user attach images and videos even when uploads are globally disabled
- **Allow markdown** — on by default; off renders all post bodies as plain text
- **Allow links** — off by default; global master switch for `http/https` hyperlinks; individual boards also have their own toggle — both must be on for links to be permitted on a board
- **Allow post editing** — off by default; `post_edit_window_seconds` sets how long users have (default 90s, 0 = unlimited)
- **Federation enabled** — master switch for ActivityPub federation
- **mCaptcha** — set `MCAPTCHA_URL` and `MCAPTCHA_SITE_KEY` in `.env` to enable; honeypot is always active regardless

### 2. Edit your site pages

Rules and FAQ pages are created automatically. Edit them at **Mod → Pages** — full markdown support, live preview before saving. Add additional pages (About, Privacy Policy, etc.) via **Admin → Site Pages**; tick **Show in footer** to include them in the site footer.

### 3. Community pruning schedule

The community pruning task (`core.tasks.prune_inactive_communities`) is created automatically when migrations run — no manual setup needed. It runs daily at 3am UTC. You can adjust the schedule or disable it via **Admin → Periodic Tasks**.

Private-message conversations have the same kind of task (`core.tasks.prune_inactive_conversations`), also created automatically, running daily at 3:30am UTC. It's disabled by default (`SiteSettings.private_message_retention_days = 0`) — set a number of days under **Admin → Site Settings → Private Messages** to turn it on.

### 4. Create your first board

**Admin → Boards → Add Board.** Set slug, name, icon emoji, description. Toggle **Allow federation** off to keep a board local-only — it won't appear in the instance discovery endpoint and its threads won't be delivered to remote instances.

### 5. Set up federation (optional)

Set `FEDERATION_BASE_URL` in your `.env` to your instance's public URL. Then go to **Mod → Federation** to connect remote instances and map their boards to your local boards. See [DEPLOYMENT.md](DEPLOYMENT.md) for help choosing your deployment path, then [DEPLOYMENT_CLEARNET.md](DEPLOYMENT_CLEARNET.md) or [DEPLOYMENT_ONION.md](DEPLOYMENT_ONION.md) for the full guide. Federation specifics are in [DEPLOYMENT_FEDERATION.md](DEPLOYMENT_FEDERATION.md).

### 6. Set up staff roles (optional)

**Admin → Roles** — define tiers with capability flags. Assign a `Role` to a user and, for non-admin tiers, the specific boards they cover via **Admin → Users → board_assignments**.

| Flag | What it grants |
|---|---|
| `can_hide` | Hide/unhide content (reversible) |
| `can_quarantine` | Quarantine content (invisible to all, DB preserved) |
| `can_purge` | Permanently delete quarantined content (hard-gated to admin-tier in code) |
| `can_lock_threads` | Lock/unlock threads |
| `can_pin_threads` | Pin/unpin threads and toggle comments disabled |
| `can_resolve_reports` | Action moderation queue reports |
| `can_suspend` | Issue timed suspensions |
| `can_ban` | Issue permanent bans |
| `can_manage_roles` | Assign roles to other users |
| `can_manage_pages` | Create and edit site pages (Rules, FAQ, custom pages) via Mod → Pages |

### 7. Activity tiers

**Admin → Activity Tiers** — customise user activity labels. Defaults: Lurker → Regular → Veteran → Prolific Poster → Legend.

### 8. Word filters (Duck Roll)

**Admin → Word Filters → Add.** Set pattern, replacement, and scope (site-wide or board-specific). Toggle regex for pattern matching.

---

## Production Deployment

### Self-hosted — Tor hidden service

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, POSTGRES_PASSWORD, FEDERATION_BASE_URL
docker compose -f docker-compose.prod.yml -p facechan-prod up -d --build

# Find your .onion address:
docker compose -f docker-compose.prod.yml -p facechan-prod logs tor
```

Always use `-p facechan-prod` with the prod compose file — keeps volumes separate from dev.

**Back up the `tor_keys` Docker volume.** It holds your onion private key. Lose it and your .onion address is gone forever — and your federation identity along with it.

### Clearnet — Railway / VPS

Set environment variables in the Railway dashboard or your `.env`. Set `FEDERATION_BASE_URL` to your public domain. For media storage on clearnet, configure Cloudflare R2.

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `SECRET_KEY` | Django secret key — long random string, **no `$` signs** | ✅ |
| `DEBUG` | `True` for dev, `False` for prod | |
| `ALLOWED_HOSTS` | Comma-separated hostnames | |
| `DATABASE_URL` | Postgres connection URL | ✅ |
| `POSTGRES_PASSWORD` | Used by Docker Compose to init Postgres | ✅ |
| `CSRF_TRUSTED_ORIGINS` | Your domain e.g. `https://example.com` | ✅ |
| `REDIS_URL` | Redis URL for WebSocket channel layer | |
| `CELERY_BROKER_URL` | Redis URL for Celery | |
| `FEDERATION_BASE_URL` | Canonical public URL of this instance — no trailing slash | |
| `MCAPTCHA_URL` | URL of your self-hosted mCaptcha instance — enables mCaptcha if set | |
| `MCAPTCHA_SITE_KEY` | mCaptcha site key — must be set alongside `MCAPTCHA_URL` | |

---

## Project Structure

```
FaceChan/
├── core/                      # Main Django app
│   ├── models.py              # User, Board, Thread, Post, Community,
│   │                          #   Report, SiteSettings, ActivityTier, ...
│   ├── views.py               # DRF viewsets and API views
│   ├── serializers.py         # DRF serializers (word filter applied here)
│   ├── consumers.py           # WebSocket consumers (notifications + board)
│   ├── routing.py             # WebSocket routing (/ws/notifications/, /ws/boards/<slug>/)
│   ├── signals.py             # post_save hooks (thread culling, federation delivery)
│   ├── permissions.py         # Moderation permission resolver
│   ├── tasks.py               # Celery tasks (community pruning, conversation pruning)
│   └── management/commands/
│       ├── seed.py
│       └── prune_communities.py
├── federation/                # ActivityPub federation app
│   ├── models.py              # Actor, RemoteInstance, RemoteActor, Follow,
│   │                          #   RemoteBoard, RemoteBoardMapping, FederationActivity
│   ├── views.py               # AP endpoints (Actor, Inbox, Outbox, Webfinger, /ap/instance)
│   ├── api_views.py           # Federation management API (admin-only)
│   ├── inbound.py             # Inbound Create(Note) handler → local Thread
│   ├── tasks.py               # deliver_accept, deliver_create_thread, fetch_instance_boards
│   ├── signatures.py          # HTTP Signatures (sign + verify)
│   ├── fetch.py               # Remote actor fetch + signed delivery
│   ├── utils.py               # AP JSON builders (Actor, Note, Create, Accept)
│   ├── signals.py             # Auto-fetch boards on instance approval
│   └── admin.py               # Full admin for all federation models
├── facechan/
│   ├── settings.py
│   ├── asgi.py
│   ├── celery.py
│   └── urls.py
├── frontend/src/
│   ├── pages/
│   │   ├── mod/
│   │   │   ├── FederationDashboard.jsx   # /mod/federation — instance + mapping UI
│   │   │   ├── ModQueue.jsx
│   │   │   ├── ModQuarantine.jsx
│   │   │   └── ModUsers.jsx
│   │   ├── Conversations.jsx             # /messages — private message inbox
│   │   ├── ConversationDetail.jsx        # /messages/:id — one conversation
│   │   └── ...
│   ├── context/
│   └── api/
├── docker-compose.yml
├── docker-compose.prod.yml
├── COMPLIANCE.md
├── DEPLOYMENT.md          # Choosing your deployment path
├── DEPLOYMENT_CLEARNET.md # VPS / PaaS clearnet deployment guide
├── DEPLOYMENT_FEDERATION.md # ActivityPub federation guide (all deployment types)
├── DEPLOYMENT_ONION.md    # Tor hidden service deployment & security guide
├── DONATE.md
└── ROADMAP.md
```

---

## API Endpoints

### Public

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/site-settings/` | Site config |
| GET | `/api/pages/` | Footer pages list |
| GET | `/api/pages/:slug/` | Single site page |
| GET | `/api/boards/` | List boards |
| GET | `/api/threads/` | Thread list (`?board=`, `?search=`) |
| GET | `/api/threads/:id/` | Thread detail + posts |
| GET | `/api/feed/` | Personalised feed |
| GET | `/api/communities/` | List communities |
| GET | `/api/users/:username/` | Public profile |

### Authenticated

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/threads/` | Create thread |
| POST | `/api/threads/:id/watch/` | Toggle watch |
| POST | `/api/threads/:id/react/` | React to thread |
| POST | `/api/threads/:id/report/` | Report thread |
| POST | `/api/threads/:id/posts/` | Reply |
| PATCH | `/api/threads/:id/posts/:id/edit/` | Edit own post (within window) |
| GET/PATCH | `/api/me/` | Own profile |
| POST | `/api/me/password/` | Change password |
| POST | `/api/me/avatar/` | Upload avatar |
| GET | `/api/me/watched/` | Watched threads + unread |
| GET | `/api/me/permissions/` | Staff role + capabilities |

### Private messages (authenticated)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/conversations/` | List your conversations, with per-conversation unread count |
| POST | `/api/conversations/` | Start a conversation (`participants`: usernames, `body`: first message) |
| GET | `/api/conversations/:id/` | Conversation detail + messages (participant, or audited staff override) |
| POST | `/api/conversations/:id/leave/` | Leave a conversation |
| POST | `/api/conversations/:id/add-participant/` | Add a participant (any current participant can) |
| POST | `/api/conversations/:id/remove-participant/` | Remove a participant (any current participant can, not yourself) |

Sending a message reuses the ordinary reply endpoint — `POST /api/threads/:id/posts/` — with the conversation's id as `:id`, gated to participants only. See `COMPLIANCE.md` → "Private messages" for the staff-access override and retention settings.

### Staff / moderation

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/mod/queue/` | Report queue |
| POST | `/api/mod/reports/:id/resolve/` | Action report |
| GET | `/api/mod/quarantine/` | Quarantined content |
| POST | `/api/mod/quarantine/:type/:id/action/` | Restore or purge |
| POST | `/api/mod/users/:id/action/` | Suspend / ban |
| GET/PATCH | `/api/pages/:slug/edit/` | Edit a site page (requires `can_manage_pages`) |

### Federation (admin-only)

| Method | Endpoint | Description |
|---|---|---|
| GET/PATCH | `/api/federation/status/` | Master switch + counts |
| GET/POST | `/api/federation/instances/` | List / add remote instances |
| GET/PATCH/DELETE | `/api/federation/instances/:id/` | Instance detail |
| POST | `/api/federation/instances/:id/refresh/` | Re-fetch board list |
| GET | `/api/federation/instances/:id/boards/` | Cached remote boards |
| GET/POST | `/api/federation/mappings/` | Board mappings |
| GET/PATCH/DELETE | `/api/federation/mappings/:id/` | Mapping detail |
| GET | `/api/federation/local-boards/` | Local boards for dropdown |

### ActivityPub (public)

| Endpoint | Description |
|---|---|
| `/.well-known/webfinger` | Actor discovery |
| `/ap/instance` | Instance info + federated board list |
| `/ap/boards/:slug` | Board Group Actor |
| `/ap/boards/:slug/inbox` | Receive inbound activities |
| `/ap/boards/:slug/outbox` | Published threads |
| `/ap/boards/:slug/followers` | Follower collection |
| `/ap/users/:username` | User Person Actor |

**WebSocket:**
- `ws[s]://<host>/ws/notifications/?token=<token>` — per-user notification push
- `ws[s]://<host>/ws/boards/<slug>/` — board-scoped new thread push

---

## Federation

FaceChan implements ActivityPub (W3C standard) for instance-to-instance federation.

**How it works:**
- Each board is a **Group Actor** — followable from any ActivityPub server
- New threads and replies by account holders are delivered as **Create(Note)** activities to all approved followers
- Replies carry `inReplyTo` pointing at the parent thread's canonical AP URL — remote instances can reconstruct the thread tree
- Inbound threads and replies from remote instances are filed under local boards via operator-configured mappings; stub user accounts are created for remote authors (`is_remote=True`, cannot log in)
- Anonymous posts (no account) stay local — they have no author Actor to attach to
- Board views update in real time when federated threads arrive — `BoardDetail.jsx` listens on `ws/boards/<slug>/` and prepends new threads without a page refresh
- All inbound/outbound activities are logged to `FederationActivity` for audit

**Three levels of control:**
1. `SiteSettings.federation_enabled` — master switch, pauses everything
2. `Board.allow_federation` — per-board opt-out
3. Post/thread author — anonymous posts never federate regardless of board settings

**Instance discovery:**
- `GET /ap/instance` — public endpoint listing all federated boards; remote instances use this to discover your boards
- When you approve an instance, FaceChan automatically fetches their board list so you can set up mappings via the dashboard

**Operator workflow:**
1. Mod → Federation → Add instance (paste domain)
2. Approve it — board list fetches automatically
3. Map their boards to yours via dropdown — this follows the remote board, so its threads start being delivered to you
4. Done — threads and replies flow in real time

See [DEPLOYMENT.md](DEPLOYMENT.md) for help choosing between clearnet, onion-only, and dual-stack deployments.

Looking for other instances to federate with? See [INSTANCES.md](INSTANCES.md).

---

## Moderation

Three independent authority scopes: **site role**, **community membership**, **community creator**.

**Content removal tiers:**

| Tier | Who | Effect |
|---|---|---|
| Hide | Mods (board-scoped) | Reversible. Visible to author and staff. |
| Quarantine | Board-admin tier+ | Invisible to all. DB preserved. |
| Purge | Admin-tier only (hard-gated in code) | Irreversible. |

**Sanctions** take effect immediately — token revoked on next request.

**Report audit survives purge** — FK goes `NULL` on purge but queue retains full context.

---

## Safety & Compliance

- **Universal floor** — CSAM scan checkpoint on every image and video upload (documented stub — see `core/csam_detection.py`). pHash stored unconditionally for retroactive scanning.
- **Jurisdictional layer** — content reporting, age confirmation, NSFW age-gating, transparency page; all configurable, all on by default.
- **NSFW board gating** — NSFW boards do not appear in the board list for logged-out users. Login and age confirmation are both required before an NSFW board is visible at all. A user who has previously confirmed their age but is not logged in still cannot see NSFW boards.
- **Federation compliance** — allowlist-only federation; no open inbound activities; full audit log.

**If you run an instance, you are the service provider.** See [COMPLIANCE.md](COMPLIANCE.md). None of this is legal advice.

---

## Philosophy

Built as a gift. No VC funding, no ad model, no data harvesting. Fork it. Run your own instance. Make it yours. Federate with others.

## Fork it, don't just download it

If you are planning to run FaceChan or build on it, fork the repository rather than cloning it directly. It takes one extra click on GitHub and it makes a real difference.

**For you:**

When you fork, you have your own copy of the codebase under your own account. Your customisations live there safely. When FaceChan updates — a bug fix, a new feature, a security patch — you pull it into your fork on your terms, not because a `git pull` overwrote something you changed. You stay in control of what goes into your instance and when.

If you hit a bug and fix it, getting that fix back upstream is straightforward — your fork is already the starting point for a pull request. You don't have to do anything extra to be a contributor. You already are one.

**For everyone:**

Forks are visible. A project with a healthy fork count signals to other potential operators that real people are running this, building on it, and trusting it enough to make it their own. That matters when someone is deciding whether to invest time in setting up an instance.

More practically: when operators fix bugs, add translations, build tooling, or improve documentation in their forks, that work can flow back. The whole ecosystem gets better. That doesn't happen when everyone is working from a private download on their own machine.

**How:**

Hit the Fork button on the [FaceChan GitHub page](https://github.com/goodcountry/FaceChan). Clone your fork. Add the upstream as a remote so you can pull in updates:

```bash
git remote add upstream https://github.com/goodcountry/FaceChan.git
```

That's it. You now have your own version and a line back to the source.

## Contributing

PRs welcome. No CoC. Just don't be a weapon.

## Licence

MIT — do what you want with it.
