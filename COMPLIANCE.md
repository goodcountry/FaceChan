# Compliance & Operator Responsibility

FaceChan is a general-purpose, self-hostable platform for community discussion and
free expression. It is distributed as source code under the MIT licence. This
document explains the project's compliance-by-design philosophy and — importantly —
where responsibility sits.

---

## The short version

**If you deploy and run a FaceChan instance, _you_ are the service provider.**
The legal duties that attach to running an online service attach to **you, the
operator** — not to the author of this software. This is true under the UK Online
Safety Act, the EU Digital Services Act, and equivalent regimes elsewhere: they
regulate *providers of services*, not authors of software.

You are solely responsible for determining and meeting the legal obligations that
apply to your instance in your jurisdiction. Nothing in this repository is legal
advice. If you intend to run a public instance, get advice from a qualified lawyer
in your country first.

---

## Compliance by design

FaceChan ships with safety and compliance tooling **enabled by default**. An
operator has to make a deliberate choice to change that. The defaults represent the
safest posture, not the most permissive one.

The reason these features are *configurable* at all is that legal requirements
genuinely differ by jurisdiction. A US-based operator relying on Section 230 host
protections has different obligations from a UK operator under the OSA, who has
different obligations again from an operator in a country with no equivalent regime.
The configuration surface reflects that legitimate legal diversity. It is **not** an
invitation to evade the law — it is a tool to operate lawfully wherever you are.

### Two layers

FaceChan separates safety into two distinct layers:

**1. The universal floor — never optional.**
Some things are wrong and illegal essentially everywhere, and the software treats
them as a permanent, non-configurable baseline:

- Child sexual abuse material (CSAM): every image upload (threads, posts, and
  avatars) passes through a mandatory checkpoint (`core/csam_detection.py`)
  before being persisted. There is no `SiteSettings` toggle for it and never
  will be.

  **What the pipeline currently does (and doesn't do):**

  1. Every image is cleaned: EXIF stripped, resized, re-encoded as WebP.
  2. A **perceptual hash (pHash)** (Meta's open-source 256-bit hashing algorithm,
     the modern standard for CSAM hash-matching) is computed and stored on the
     model (`Thread.image_pdq_hash`, `Post.image_pdq_hash`,
     `User.avatar_pdq_hash`). This hash persists permanently alongside the image.
  3. `scan_image()` is called — but currently does nothing. It always returns
     `NOT_IMPLEMENTED` and logs that loudly. **No actual detection occurs.**
  4. Because no provider is configured, uploads are never blocked by this
     checkpoint. A real detection provider must be wired into `scan_image()`
     before this becomes working protection.

  **Why the hashes are stored even now:** once a provider integration is live,
  stored pHashes allow retroactive scanning of existing content without
  reprocessing or re-downloading images. A management command can query the
  provider against all stored hashes in bulk. This is why hash generation is
  unconditional — not gated on provider availability.

  **What operators must do:**
  Real hash-matching works against databases maintained by NCMEC, the IWF, or
  commercial equivalents (Microsoft PhotoDNA, Thorn Safer, Google CSAI Match).
  Access requires a formal vetted agreement — it is not a library you pip
  install. Read `core/csam_detection.py` in full for the step-by-step
  integration checklist, and do not represent an instance as having CSAM
  detection until that work is complete.

  Regardless of detection tooling, UK operators should register with the NCA's
  CEOP/CSEA reporting portal; US operators with NCMEC's CyberTipline. That
  reporting obligation exists independent of automated detection.

  Note that a CSAM match does not automatically mean the content should be
  purged on sight — see "Content removal: hide, quarantine, purge" below.
  What you are actually required to do with matched content, including
  evidence-preservation obligations, requires jurisdiction-specific legal
  advice rather than a default assumed by this software.

**2. The jurisdictional layer — configurable, safe by default.**
These are controlled from **Admin → Site Settings → Safety & Compliance** and ship
ON:

| Setting | Default | What it does |
|---|---|---|
| `jurisdiction_mode` | `uk` | Declares your operating jurisdiction; surfaced in transparency info |
| `enable_content_reporting` | on | Report control on threads/posts → moderation queue |
| `require_age_confirmation` | on | Age confirmation at registration |
| `minimum_age` | 18 | Minimum age users confirm |
| `block_nsfw_without_age_gate` | on | NSFW boards require login **and** age confirmation — hidden from all logged-out users regardless of any prior age confirmation |
| `publish_transparency_info` | on | Public transparency page (jurisdiction, contact, reporting routes) |
| `moderation_contact` | — | Public contact for reports / legal enquiries |

An operator outside the UK/EU may legitimately turn some of these off if their law
does not require them. That is their decision and their responsibility.

**NSFW boards — what the gating actually does:**

FaceChan's NSFW gate is deliberately strict. A board marked NSFW is completely invisible in the board list to any user who is not both logged in and age-confirmed. This is not just a content warning — the board does not appear at all. A logged-out user who previously clicked through an age gate still cannot see NSFW boards until they log in.

This means a visitor who stumbles across an instance, or follows a link, will never see adult content without having first created an account and confirmed their age. The design intent is that legal adult content is available to consenting adults who have opted in, and is not incidentally visible to anyone else.

What operators permit on NSFW boards is their decision and their legal responsibility. FaceChan ships with no content rules beyond the universal floor (CSAM). Operators are responsible for ensuring that what they allow complies with the law in their jurisdiction — including any obscenity laws, regulations on extreme content, and age verification requirements that may apply in their territory.

---

## Content removal: hide, quarantine, purge

FaceChan does not have a single "delete" action for moderators. There are three,
deliberately separated by how reversible they are and who can use them — see
`core/permissions.py` for the implementation.

**Hide** (mods, janitors, board-scoped). Reversible. Content stays in the database
and remains visible to its own author and to staff with reach over it — it's just
excluded from public listings. The lowest-stakes action, intended for routine
moderation (spam, low-grade rule-breaking) where a mistake costs nothing.

**Quarantine** (board-admin tier and above, board-scoped). Reversible, but stronger:
content becomes invisible to *everyone*, including its own author, and stays in the
database pending an admin decision to restore or purge. This tier exists for a
reason that isn't really a software question. Content a moderator removes might be
something a law enforcement authority would need preserved, and in some
jurisdictions even the act of deleting certain material could itself carry legal
weight that hasn't been assessed for your situation. Quarantine means a single
non-admin moderation action can't make that judgement call by accident — it holds
the content rather than destroying it, and pushes the harder decision up to whoever
is accountable for the instance.

**Purge** (admin-tier only, hard-enforced in code regardless of any role flag).
Irreversible. The row is actually deleted. This is the only point in the system
where content genuinely disappears, and it requires the highest level of authority
on the instance to invoke.

**What this is and isn't.** This tiering is architecture, not a retention policy.
FaceChan does not impose a minimum or maximum retention period on quarantined
content, does not automatically notify any authority when something is quarantined
or purged, and does not tell you how to handle material that might be evidentiary.
Those are exactly the kind of jurisdiction-specific questions raised earlier in this
document — what you're required to keep, for how long, how it needs to be handled
to remain usable if a law enforcement authority does want it, and whether retaining
something illegal is itself a problem where you operate. None of that is settled by
this codebase, and none of it should be assumed from the existence of a "quarantine"
button. If your instance might encounter content with real legal stakes, get advice
on retention and handling specifically, before you need it.

**The `Report` row itself is the part designed to survive purge.** Purging content
sets `Report.thread`/`Report.post` to `NULL` (`SET_NULL`, not `CASCADE`) so the
record of who reported what, who actioned it, and why isn't destroyed along with
the content. `Report` also snapshots the reported user, board, content type, and a
short preview at the moment the report is *filed* — before any moderator has acted
on it — specifically so that record doesn't depend on the live thread/post still
existing later. This is still just a record inside the application database, not a
preservation or evidence-handling system; it doesn't substitute for whatever your
jurisdiction actually requires if law enforcement does come asking.

---

## IP address logging

FaceChan stores the submitting IP address (`poster_ip`) on every thread and post at the moment of submission. This address is also snapshotted into the `Report` row at report-filing time (`target_poster_ip`) so it survives any subsequent purge of the underlying content.

**What this is for:** abuse tracing and law enforcement cooperation. An IP address stored against a post allows an operator to respond to a lawful request from an authority identifying the likely source of a post, and to build a picture of repeat abusers across accounts.

**What operators need to know:**

- IP addresses are personal data under GDPR, the UK GDPR, and most equivalent regimes. Storing them creates data protection obligations.
- You need a lawful basis to store them. Legitimate interests (platform safety, abuse prevention) is the most common basis for this kind of logging, but it requires a legitimate interests assessment (LIA) and must be weighed against user rights.
- You need a retention policy. Storing IP addresses indefinitely is unlikely to be defensible. Decide how long you'll keep them and implement deletion — a management command or Celery task clearing `poster_ip` from old rows older than your retention window is straightforward to add.
- IP addresses are only as useful as your ISP's cooperation. Dynamic IPs, VPNs, Tor exit nodes, and CGNAT all reduce their evidential value. Do not over-rely on them as an identification tool.
- On Tor instances, `poster_ip` will always be a Tor exit node address, not the user's real IP. This is expected and by design — operators running onion instances should account for this in their expectations and any law enforcement liaison.
- Access is restricted to Django admin (superuser) only. Do not expose `poster_ip` in any API response or staff frontend view — the current implementation correctly keeps it out of all serializers.

This is orientation, not legal advice. If your instance is subject to GDPR or UK GDPR, take advice on your specific data protection obligations before going public.

---

## The author's position

The author of FaceChan distributes it as open-source software in the spirit of free
expression and self-determination. The author:

- Distributes **source code**, not a hosted service.
- Builds compliance tooling in, on by default, in good faith.
- Does **not** operate instances on behalf of anyone who deploys the code.
- Makes no warranty that any given configuration is lawful in any given place —
  that determination is the operator's.

Deploying the software is an independent act by the operator, who chooses the
configuration, the hosting, the jurisdiction, and the moderation approach.

---

## If you operate an instance

A practical, non-exhaustive starting checklist. This is orientation, not legal
advice:

1. **Identify your jurisdiction's regime** (OSA, DSA, Section 230, etc.) and get
   legal advice if your instance will be public.
2. **Wire up real CSAM detection before going public.** perceptual hash (pHash)es
   are already computed and stored for every image upload (threads, posts, and
   avatars) — that part is done. What's missing is a provider to compare them
   against. The `core/csam_detection.py` checkpoint is currently a stub: it does
   not block anything. Until you integrate a real provider (IWF hash list, NCMEC
   programme, PhotoDNA, Thorn Safer, or equivalent — all require a formal
   agreement), you are not running automated CSAM detection. Plan your moderation
   accordingly (human review, fast reporting routes) and do not represent your
   instance as protected until the integration is complete. See
   `core/csam_detection.py` for the full operator checklist.
3. **Decide your quarantine/purge process before you need it.** Quarantine holds
   content rather than destroying it — good, since it gives you time to think —
   but "I'll decide later" isn't a retention policy. Know in advance, ideally
   with legal advice, what you'll do with quarantined content: how long you'll
   hold it, what you'll do if law enforcement asks for it, and when (if ever)
   you'll purge it. Reacting to a real case in the moment, with no plan, is the
   worst time to work this out.
4. **Do a risk assessment.** UK operators: see Ofcom's guidance for smaller
   services. A template lives in `docs/risk-assessment-template.md`.
5. **Review the username change settings for your context.** Username change
   logging (`SiteSettings.enable_username_change_audit`) and the rename cooldown
   (`username_change_cooldown_days`) both ship on, with a 14-day default cooldown.
   Whether logging renames is appropriate, and what cooldown makes sense, depends
   on your moderation model and jurisdiction — there's no universal right answer
   here, just sensible defaults to start from.
6. **Set an IP address retention policy.** IP addresses are stored on every thread
   and post. They are personal data. Decide how long you'll keep them and implement
   deletion of old records. See the IP address logging section above.
7. **Consider word filters for your context.** The Duck Roll word filter
   (`Admin → Word Filters`) lets you substitute words/phrases at read time without
   touching stored content. Useful for slurs, spam phrases, or community tone-setting.
   Filters are entirely optional and operator-defined — none ship by default.
8. **Keep reporting routes open.** Leave content reporting enabled; monitor the
   moderation queue.
9. **Set a moderation contact** so users and authorities can reach you.
10. **Consider your structure.** Running a public service as a private individual
    carries personal exposure; many operators use a company. Take advice.
11. **Keep records** of your moderation decisions and risk assessment.

---

## Reporting illegal content on an instance

Each instance sets its own `moderation_contact`. Reports of illegal content should
go to that address, and — for CSAM specifically — to the relevant national authority
(NCA in the UK, NCMEC in the US) regardless of any instance-level process.

---

*This document is part of the FaceChan project and describes design intent and
operator responsibility. It is not legal advice.*
