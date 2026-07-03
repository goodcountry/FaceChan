# FaceChan — Choosing Your Deployment Path

FaceChan can be deployed in two fundamentally different ways. This document helps you choose between them. Neither is universally better — the right choice depends on who you are, where you are, and what you are trying to do.

Read this before touching any config file.

---

## The two paths

| | Clearnet | Onion |
|---|---|---|
| **Accessible via** | Any browser | Tor Browser only |
| **Operator identity** | Known to hosting provider | Strongly protected |
| **Domain** | Required ($10–15/year) | Not required |
| **TLS certificate** | Required (free via Let's Encrypt) | Not required (Tor provides encryption) |
| **Legal exposure** | Direct — you are identifiable | Significantly reduced |
| **Audience reach** | Anyone | Tor users only |
| **Federation** | Full Fediverse interoperability | Onion instances only (unless dual-stack) |
| **Performance** | Fast | Slower — Tor adds latency |
| **Ops complexity** | Lower — PaaS options available | Higher — self-managed server required |
| **Takedown risk** | Higher — hosting providers comply with legal orders | Lower — no central point of control |
| **Anonymous payment** | Not necessary | Strongly recommended |

---

## Clearnet

Your instance is reachable by anyone with a browser. You have a real domain name. You are identifiable to your hosting provider and, if compelled, to law enforcement.

**Choose clearnet if:**
- You are in a stable legal jurisdiction and intend to run a fully lawful service
- You want the widest possible audience without requiring Tor
- You want federation with Mastodon, Lemmy, and the broader Fediverse
- You are comfortable being identified as the operator
- You want the simplest day-to-day operations

**Do not choose clearnet if:**
- You are in a country where hosting a free speech platform could result in legal, political, or personal danger
- Operator anonymity is important to you
- You expect your instance to be a target for takedowns

→ **[DEPLOYMENT_CLEARNET.md](DEPLOYMENT_CLEARNET.md)**

---

## Onion (Tor hidden service)

Your instance is reachable only via Tor Browser. You have a `.onion` address derived cryptographically from keys you control — no registrar, no DNS, no one to compel. Your hosting provider may not know what you are running.

**Choose onion if:**
- You are in an environment where hosting a forum could result in arrest, detention, or violence
- Operator anonymity is essential, not optional
- You want an address that cannot be seized or transferred
- You are building toward a federated network of onion instances
- You understand and accept that your audience must use Tor Browser

**Do not choose onion if:**
- Your main goal is reaching the widest possible audience
- You want full Fediverse interoperability from day one
- You are not prepared for the additional operational complexity

→ **[DEPLOYMENT_ONION.md](DEPLOYMENT_ONION.md)**

---

## Dual-stack (both)

You can run both simultaneously. Your `FEDERATION_BASE_URL` is your clearnet domain — giving you full Fediverse federation and normal browser access. Your `.onion` address runs in parallel, giving anonymous users a way in without the friction of exposing their onion address to a clearnet DNS lookup.

Add the `Onion-Location` header to your nginx config and Tor Browser will automatically offer the onion version to visiting users:

```nginx
add_header Onion-Location http://youronionaddress.onion$request_uri;
```

**Choose dual-stack if:**
- You want maximum reach AND want to serve anonymous users well
- You are not yourself at high risk as an operator — your clearnet domain is publicly associated with the instance
- You want to participate in both the clearnet Fediverse and any emerging onion FaceChan network

**This is the recommended setup for operators in stable legal environments who care about user privacy.**

---

## A note on legal obligations

Whichever path you choose, you are the operator. The author of FaceChan is the author of the software — not the operator of your instance.

Read [COMPLIANCE.md](COMPLIANCE.md). The compliance architecture — age-gating, moderation tools, CSAM detection scaffolding, content reporting — is there for a reason. It does not operate itself. That is your job.

Know the law in your jurisdiction before you go live. The deployment guides are technical documents. They are not legal advice.

---

## Summary

| I want to... | Choose |
|---|---|
| Reach the widest audience, simplest setup | Clearnet |
| Protect my identity as operator | Onion |
| Both reach and user privacy, comfortable being identified | Dual-stack |
| Run in a high-risk environment | Onion |
| Federate with Mastodon / Lemmy | Clearnet or Dual-stack |
| Federate with other FaceChan instances only | Onion |

---


---

## Federation

ActivityPub federation works the same regardless of whether your instance is clearnet, onion, or dual-stack. See [DEPLOYMENT_FEDERATION.md](DEPLOYMENT_FEDERATION.md) for the full guide.

*FaceChan is MIT-licensed software. The author is not responsible for your deployment.*

Key points:

- **Jurisdiction of the sender is irrelevant to your liability** — what matters is what appears on your instance and what your local law says about it
- **Your moderation obligations do not shrink because content arrived via federation** — if you are subject to the UK Online Safety Act or equivalent, federated content counts
- **The allowlist is your first line of defence** — only approve instances you have some basis for trusting
- **The audit log** (Django admin → Federation → Federation activities) records all inbound activities, including their full payload, for as long as you retain the database

When in doubt, get legal advice for your jurisdiction. The author of this software is not your lawyer.

---

### Finding other instances to federate with

A community-maintained directory of known FaceChan instances is maintained in [INSTANCES.md](../INSTANCES.md) in the repository. It lists operator-submitted URLs, content policies, and federation status — useful context when deciding who to add to your allowlist.

**The author of this software does not operate, endorse, or take any responsibility for any instance listed there.** Use your judgement. The allowlist exists precisely so that you — not anyone else — decide who your instance trusts.

If no directory exists yet, the FaceChan GitHub repository is the natural place to look for community coordination. Check the issues and discussions.

---

### Federating between clearnet and onion instances

⚠️ **This has not been tested end-to-end in production. The following is how it should work in theory — treat it as a starting point for experimentation, not a guarantee.**

FaceChan's federation transport layer (`federation/fetch.py`) routes outbound requests based on the destination address:

- Requests to `.onion` addresses go via `socks5h://tor-proxy:9050`
- Requests to clearnet addresses go direct

This means mixed-mode federation is *theoretically* possible, but both sides need to be configured correctly.

**What a clearnet instance needs to reach an onion instance:**

1. The `tor-proxy` container must be running (it's in the prod compose file — don't remove it)
2. `FEDERATION_SOCKS_PROXY=socks5h://tor-proxy:9050` must be set in `.env`
3. That's it for outbound delivery — requests to `.onion` addresses will route through Tor automatically

**What an onion instance needs to reach a clearnet instance:**

Nothing extra. Tor exit nodes can reach clearnet HTTPS endpoints directly. The onion instance delivers over its normal Tor circuit.

**The harder problem — inbound HTTP signature verification:**

When a clearnet instance receives a signed ActivityPub request from an onion instance, it must fetch the sender's public key to verify the signature. That key fetch goes to a `.onion` URL. If `FEDERATION_SOCKS_PROXY` is not set on the clearnet instance, the key fetch fails and the signature cannot be verified — the activity will be rejected.

So for *inbound* activities from onion instances to work on a clearnet instance, `tor-proxy` must be running and `FEDERATION_SOCKS_PROXY` must be set, even if the clearnet instance never initiates contact with onion instances itself.

**What hasn't been tested:**

- Whether HTTP signatures verify correctly across a mixed round-trip (the `Host` header differs between onion and clearnet, and how this interacts with signature verification is untested)
- Whether nginx on a clearnet/VPS deployment correctly passes the `X-Forwarded-For` and `Host` headers through to Django in a way that signature verification can use
- Edge cases around redirects, timeouts, and Tor circuit failures mid-delivery

**If you test this and it works (or doesn't):** please open an issue or PR on the FaceChan repository documenting what you found. This is genuinely unknown territory.

---

## Summary checklist for high-risk operators

- [ ] Full-disk encryption (LUKS) enabled on the host machine
- [ ] Strong LUKS passphrase — not stored anywhere on the machine
- [ ] `panic.sh` reviewed, tested, and accessible (consider a desktop shortcut or alias)
- [ ] Firewall configured — no unnecessary open ports
- [ ] nginx bound to `127.0.0.1` only
- [ ] SSH keys only — password auth disabled
- [ ] Server purchased/rented anonymously
- [ ] Server managed only over Tor
- [ ] No personal accounts or identities used in connection with this deployment
- [ ] Log retention minimised
- [ ] `AvoidDiskWrites 1` set in torrc
- [ ] Any promotion done exclusively over Tor via throwaway accounts
- [ ] `FEDERATION_BASE_URL` set correctly for your deployment type (clearnet / onion / dual-stack)
- [ ] `ALLOWED_HOSTS` includes your onion address/domain — without this, every request returns 400 Bad Request
- [ ] Federation allowlist reviewed — no instances approved without consideration
- [ ] Federation audit log retention reviewed alongside general log policy
- [ ] If onion-only: understood that `.onion` key loss ends federation relationships; `panic.sh` does this deliberately

---

## Making your instance discoverable

Once your .onion is running, people can only find it if they know the address. This section covers how to get listed on dark web search engines and directories — and how to do it without exposing yourself.

### How dark web crawlers work

Dark web search engines work by following links, exactly like clearnet crawlers. If your .onion address appears on any already-indexed page — a forum post, a directory, another .onion site — crawlers will find it and index it automatically. You don't always need to submit directly.

### Search engines and directories

**Ahmia** (`ahmia.fi`) — the most established dark web search engine. Accessible on both clearnet and Tor. Has a manual submission form at `ahmia.fi/add/`. Once submitted it crawls automatically and is re-indexed regularly. Recommended first stop.

**Torch** — one of the oldest Tor search engines. No submission form; finds sites by crawling links. Get your address mentioned anywhere Torch already indexes and it will find you.

**Haystak** — Tor-native search engine available at `haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion`. Accepts submissions via its own interface over Tor.

**DarkSearch** — indexes .onion content and exposes a public API. Submission available through its Tor interface.

**The Hidden Wiki** — not a search engine but a heavily-trafficked link directory. Various versions exist with different editors. Getting listed here drives significant organic traffic. Search for current addresses via Ahmia or Torch — the address changes periodically.

**r/onions and r/TOR** — Reddit communities where new .onion sites are routinely shared. A post here gets your address in front of a large audience quickly and will be picked up by crawlers that index Reddit.

### Organic discovery

The most effective long-term strategy is to get your address mentioned on sites that crawlers already index:

- Post on relevant .onion forums and communities
- List on clearnet "onion link" aggregator sites
- Ask friendly .onion communities to link to you
- Include your address in FaceChan's own transparency page once the instance is established

Links beget crawls. One mention on a well-indexed site is often enough for all the major crawlers to find you within days.

### Doing it safely — the anonymity rules

Promotion is where operators most commonly make mistakes. Every submission and post creates a potential link between you and your site.

**Always use Tor Browser for any promotion activity.** Never submit to search engines or post about your site from your home or work IP — ever. Even once.

**Use throwaway accounts.** Create any Reddit, forum, or directory accounts over Tor. Never reuse an account that has any connection to your real identity. Use a different account for each platform.

**Mind the timing.** If your site goes live on a Tuesday afternoon and you post about it to Reddit on Tuesday afternoon from your home connection, that timing correlation is a data point. Introduce deliberate delay and always use Tor.

**Submit through Tor where possible.** Ahmia supports submissions via its Tor address. Prefer this over the clearnet submission form.

**Don't mention details that narrow down who you are.** Region, timezone hints, writing style, inside references — all of these can be used to correlate your promotion activity with your real identity over time.

**Let crawlers do the work where you can.** A single link posted via Tor on a well-indexed site is safer than multiple direct submissions from accounts that could be correlated.

### Summary: safe promotion checklist

- [ ] Tor Browser used for all promotion — no exceptions
- [ ] Throwaway accounts created over Tor for Reddit and any forums
- [ ] Submitted to Ahmia via its Tor address, not the clearnet form
- [ ] No timing correlation between site launch and promotion posts
- [ ] No personally identifying details in any promotion copy
- [ ] Promotion accounts not reused across platforms or linked to real identity

---

## Running a permanent onion instance on a home server

This covers the specific case of running FaceChan as a Tor hidden service on a machine you physically control — a home server, a dedicated Linux box, or a laptop that stays on. It assumes onion-only (no clearnet domain).

**How this differs from the VPS path in this guide:**

- No SSL certificate needed — Tor encrypts the connection end to end
- No domain name needed — your `.onion` address *is* your domain
- No Cloudflare R2 or external media storage needed unless you want it
- You run `docker-compose.prod.yml` directly on the machine, not over SSH

**The single most important thing: back up your Tor keys**

Your onion address is derived from a private key stored in the `tor_keys` Docker volume. Lose that volume and your onion address is gone permanently — there is no recovery, no way to reclaim it. Anyone who had bookmarked or federated with your instance will lose you.

Back up the volume contents to your encrypted storage immediately after first boot, and again any time you intentionally rotate keys. On Linux:

```bash
# Find where Docker stores the volume
docker volume inspect facechan-prod_tor_keys

# Copy the _data directory to your encrypted backup location
sudo cp -r /var/lib/docker/volumes/facechan-prod_tor_keys/_data /path/to/encrypted/backup/tor_keys
```

Keep this backup somewhere that survives a reinstall — inside your VeraCrypt volume is ideal.

**Step by step:**

```bash
# 1. Mount your encrypted volume and navigate to your working directory
# 2. Clone the repo
git clone https://github.com/goodcountry/FaceChan.git
cd FaceChan

# 3. Create your .env from the example
cp .env.example .env
# Edit .env — set SECRET_KEY, POSTGRES_PASSWORD, DEBUG=False
# Leave FEDERATION_BASE_URL blank for now

# 4. Start the stack
docker-compose -f docker-compose.prod.yml -p facechan-prod up -d --build

# 5. Get your onion address
docker-compose -f docker-compose.prod.yml -p facechan-prod logs tor | grep "onion"
# Or check the hostname file directly:
docker-compose -f docker-compose.prod.yml -p facechan-prod exec tor cat /var/lib/tor/hidden_service/hostname

# 6. Add the onion address to .env
# FEDERATION_BASE_URL=http://youronionaddress.onion
# ALLOWED_HOSTS=localhost,127.0.0.1,youronionaddress.onion

# 7. Restart to pick up the new env
docker-compose -f docker-compose.prod.yml -p facechan-prod up -d

# 8. Create your admin account
docker-compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py createsuperuser
docker-compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py grant_admin <username>

# If you ever need to reset a password from the command line (e.g. locked out of admin):
#
# Option A — Django changepassword (interactive, type password when prompted).
# Avoid ! in the password or run `set +H` first to disable bash history expansion,
# otherwise bash will mangle the password before it reaches Django:
#
#   set +H
#   docker-compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py changepassword <username>
#
# Option B — Python shell (safest, handles any character including !):
#
#   docker-compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py shell -c \
#     "from django.contrib.auth import get_user_model; U = get_user_model(); \
#      u = U.objects.get(username='<username>'); u.set_password('<newpassword>'); \
#      u.save(); print('done')"
#
# Note: passwords changed via the Django admin panel are not affected by this bash issue
# and handle all special characters correctly.

# 9. Back up your Tor keys NOW
docker volume inspect facechan-prod_tor_keys
```

**Keeping it running**

Docker will restart containers automatically on reboot (`restart: unless-stopped` is set in the prod compose). You do not need to do anything on reboot other than ensure Docker is running and, if your working directory is on an encrypted volume, that the volume is mounted before Docker tries to start.

If you use a VeraCrypt volume for the repo and media, you need the volume mounted before Docker starts. Either mount it manually after login, or set up your machine so the encrypted volume mounts as part of the boot sequence — how you do this depends on your setup and threat model.

**NordVPN or other VPN with a kill switch**

If you run a VPN with a kill switch on the host machine, it may block Docker's internal network traffic (Docker uses `172.16.0.0/12` bridge addresses). This will make containers unreachable from the host even though container-to-container traffic works fine. The fix:

```bash
nordvpn allowlist add subnet 172.16.0.0/12
```

The onion delivery path is container-to-container and is unaffected either way — this only matters if you want to reach the instance from the host machine's browser.

**Full details**

The prod compose file, nginx config, and Tor setup are documented throughout this guide. For testing federation between two local onion instances before going live, see [`test-federation/TESTING.md`](test-federation/TESTING.md) — the test stack is prod-equivalent and the walkthrough there covers the two-instance setup in detail.

---

## Testing federation before you go live

Before exposing your instance to the world it's worth verifying that federation actually works — that your instance can discover remote boards, send Follow activities, and receive federated threads in real time.

The repo includes a complete guide for spinning up two independent FaceChan instances on the same machine, each as a Tor hidden service, federating with each other over Tor exactly as two real-world instances would. No external servers needed, no DNS, no clearnet exposure.

See [`test-federation/TESTING.md`](test-federation/TESTING.md) for the full step-by-step. It covers:

- Preparing two isolated Docker Compose stacks with separate databases, Redis instances, and Tor containers
- Getting stable onion addresses for each instance
- The first-boot sequence (superuser, grant_admin, board creation)
- Wiring up the two-way federation (add remote, approve, map boards, verify Follow/Accept)
- Troubleshooting the common failure points (NordVPN kill switch, Redis channel layer, Tor SOCKS proxy)

The whole thing runs on a single Linux machine. If you can get two local onion instances federating, a real deployment will work.

---

*FaceChan is MIT-licensed software. The author is not responsible for your deployment. Stay safe.*

**`docker-compose` fails with `ModuleNotFoundError: No module named 'distutils'`** —
Ubuntu 24.04 ships Python 3.12, which dropped `distutils` from the standard
library. The `docker.io`-packaged `docker-compose` (v1.29.2) still depends on it.
Try `sudo apt install python3-setuptools -y` first. If that doesn't resolve it,
switch to the Compose v2 plugin: `sudo apt remove docker-compose -y && sudo apt
install docker-compose-v2 -y`, then use `docker compose` (space) instead of
`docker-compose` (hyphen) for all commands on that machine.
