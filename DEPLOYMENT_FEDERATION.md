# FaceChan — Federation Guide

FaceChan supports ActivityPub — the protocol that powers Mastodon, Lemmy, and the broader Fediverse. Federation lets boards on different instances follow each other so threads propagate across a network of servers. No central authority controls this. No registration is required.

This guide covers everything that applies regardless of whether your instance is on clearnet, onion, or dual-stack. For deployment-specific differences see:

- [DEPLOYMENT_CLEARNET.md](DEPLOYMENT_CLEARNET.md) — clearnet and dual-stack federation setup
- [DEPLOYMENT_ONION.md](DEPLOYMENT_ONION.md) — onion-specific configuration (http vs https, SOCKS proxy, .onion identity)

---

## How federation works

Federation is **opt-in**. If you do not set `FEDERATION_BASE_URL`, the federation layer still runs but your instance will not be reachable by remote servers. Local operation is unaffected either way. A notice appears in the Django logs and in the federation dashboard at `/mod/federation` as a reminder.

### What `FEDERATION_BASE_URL` is

It is the canonical public address of your instance — the URL remote servers use to find your boards and deliver activities. It must be publicly reachable by any instance you want to federate with.

This is just your server's address. You do not register it anywhere. There is no ActivityPub registry. Remote servers discover your boards by fetching URLs under this base — for example `https://yourdomain.tld/ap/boards/g` for your `/g/` board.

Set it in your `.env`:

```
FEDERATION_BASE_URL=https://yourdomain.tld
```

No trailing slash. The scheme must match how your server is actually reachable — `https://` for clearnet with TLS, `http://` for onion (Tor provides transport encryption natively).

---

## The instance allowlist

FaceChan does **not** do open federation. Incoming activities from unknown instances are automatically queued as `pending` and rejected until you approve them.

This is a deliberate compliance decision. Open federation means you receive content from servers you know nothing about, created by people you have no relationship with, potentially illegal in your jurisdiction. The allowlist puts you in control.

**To approve a remote instance:**

1. Go to Django admin → Federation → Remote instances
2. Find the pending instance (it appears automatically when they first contact you)
3. Set status to `Approved` and save

Only approved instances can deliver activities to your inboxes or receive federated content from your boards.

**To proactively add an instance** (before they contact you):

Add a `RemoteInstance` entry manually in Django admin with the remote domain and set status to `Approved`. Their Follow requests will then be accepted automatically when they arrive.

---

## What federates and what does not

| Content | Federates? | Notes |
|---|---|---|
| Threads by account holders | Yes | Delivered to all approved followers on thread creation |
| Anonymous threads | No | Stay local — no author Actor to attach to |
| Post replies | Yes | Delivered to the thread's followers and, for replies on a remotely-originated thread, back to that thread's origin server too |
| NSFW boards | Yes, flagged | Remote instances receive the `nsfw: true` flag and can filter accordingly. The same age-verification requirement applies to federated NSFW content on the receiving instance. |

Anonymous posting is a core FaceChan feature and it is preserved — anonymous threads simply do not leave your instance. Account holders post pseudonymously; their Actor is `@username@yourdomain.tld`, which reveals nothing about their real identity.

---

## Relay federation (optional)

By default, each instance only delivers content it originated. If three instances want to federate with each other, every instance must follow every other instance directly — a full mesh.

**Relay federation** is an alternative: an instance re-forwards content it receives onward to its own followers, building a chain instead of requiring a full mesh. With relay on, a simple ring (1→2, 2→3, 3→1, each instance only following the one before it) is enough for a post made on instance 1 to eventually reach instance 3, relayed via instance 2.

This is off by default — the simpler, safer mode (full mesh, no relaying) has fewer moving parts and a smaller audit surface. Turn relay on deliberately if you're building a larger web of instances and a full mesh isn't practical.

**To enable:** Django admin → Site settings → Federation → tick `relay_federation_enabled`. `max_relay_hops` (default 5) caps how many instance-to-instance hops a relayed post can travel before this instance stops forwarding it further, regardless of anything else.

**How duplicates are prevented:** a relayed post keeps its original Note ID and original author from the very first instance it was posted on — it is never reissued as a new post from the relaying instance's own identity. Every instance an activity passes through is recorded in the activity itself, and an instance will never relay a post to an instance already in that list. This is what stops a ring topology from looping a post back to where it started, or from a post arriving at the same instance twice via two different paths and being duplicated. The hop limit is a second, blunter backstop for the same problem, in case a non-FaceChan ActivityPub server somewhere in the chain doesn't preserve this metadata.

**What you'll see:** relayed posts show their true original author (`@username@origin-instance.onion`), not the relaying instance. In the Federation activities audit log (Django admin → Federation → Federation activities), outbound entries have an `is_relay` column/filter — `True` for posts being relayed onward, `False` for posts that originated on your instance.

---

## Your federation identity

Your federation identity is whatever is in `FEDERATION_BASE_URL` — your domain on clearnet, your `.onion` address on onion-only. Losing it severs all your federation relationships permanently.

**Clearnet:** your domain name is your identity. If your domain expires, is seized, or your registrar is compelled to transfer it, remote instances that followed you can no longer reach your Actor URLs. Keep registration paid. Use a registrar with a strong privacy record.

**Onion-only:** your `.onion` address is derived from a private key stored on disk. Losing or destroying that key ends your federation identity with no recovery. Back up the key volume or accept that it is gone if the machine is lost.

---

## Legal exposure from federation

Receiving federated content means content you did not create will appear on your server. Your allowlist controls who can send it, but you cannot fully control what approved instances deliver. Your existing moderation tools — hide, quarantine, purge — apply to federated content just as they do to local content.

Key points:

- **Jurisdiction of the sender is irrelevant to your liability** — what matters is what appears on your instance and what your local law says about it
- **Your moderation obligations do not shrink because content arrived via federation** — federated content counts the same as local content under most content liability frameworks
- **The allowlist is your first line of defence** — only approve instances you have some basis for trusting
- **The audit log** (Django admin → Federation → Federation activities) records all inbound activities including their full payload for as long as you retain the database

When in doubt, get legal advice for your jurisdiction. The author of this software is not your lawyer.

---

## Finding other instances to federate with

A community-maintained directory of known FaceChan instances is in [INSTANCES.md](INSTANCES.md). It lists operator-submitted addresses, content policies, and federation status — useful context when deciding who to add to your allowlist.

The author of this software does not operate, endorse, or take any responsibility for any instance listed there. Use your judgement. The allowlist exists precisely so that you — not anyone else — decide who your instance trusts.

---

## Testing federation before you go live

Before exposing your instance to the world it is worth verifying that federation actually works — that your instance can discover remote boards, send Follow activities, and receive federated threads in real time.

The repo includes a complete guide for spinning up two independent FaceChan instances on the same machine, each as a Tor hidden service, federating with each other over Tor exactly as two real-world instances would. No external servers, no DNS, no clearnet exposure needed.

See [`test-federation/TESTING.md`](test-federation/TESTING.md) for the full step-by-step. It covers:

- Preparing two isolated Docker Compose stacks with separate databases, Redis instances, and Tor containers
- Getting stable onion addresses for each instance
- The first-boot sequence (superuser, grant_admin, board creation)
- Wiring up two-way federation (add remote, approve, map boards, verify Follow/Accept)
- Troubleshooting the common failure points (NordVPN kill switch, Redis channel layer, Tor SOCKS proxy)

The whole thing runs on a single Linux machine. If you can get two local onion instances federating, a real deployment will work.

---

## Federation checklist

- [ ] `FEDERATION_BASE_URL` set correctly and matches your actual reachable address
- [ ] Federation enabled in Django admin → Site settings if you want to participate
- [ ] At least one board has `allow_federation` enabled
- [ ] Instance allowlist reviewed — no instances approved without consideration
- [ ] Federation audit log retention reviewed alongside your general log policy
- [ ] Moderation workflow covers federated content, not just local posts
- [ ] Federation identity (domain or .onion key) backed up or loss consequences understood

---

*FaceChan is MIT-licensed software. The author is not responsible for your deployment.*
