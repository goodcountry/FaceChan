# FaceChan — Onion Deployment & Security Guide

> **Choosing your deployment path?** See [DEPLOYMENT.md](DEPLOYMENT.md) first.

This document covers secure deployment of FaceChan, with particular focus on operators in high-risk environments — countries where hosting a free speech platform could result in legal, political, or personal danger.

---

## Who this is for

FaceChan is self-hostable software. The author is not involved in your deployment and takes no responsibility for how you use it. This guide exists because some people who want to run this software may face genuine physical or legal danger for doing so .

**This guide is written for operators in environments where free expression is suppressed by the state.**

That means:

- Journalists, activists, and organisers operating under authoritarian governments where hosting a forum can result in arrest, detention, or violence
- Communities in countries where discussing certain topics — political opposition, LGBTQ+ identity, religious minorities, labour organising — is criminalised
- Whistleblowers and sources who need an infrastructure that cannot easily be seized or traced back to them
- People operating in conflict zones or under martial law where normal legal protections do not apply

**This guide is not an invitation to break the law in democratic countries.**

FaceChan operates within the law, and operators in the UK, US, EU, and similar jurisdictions are expected to do the same. The compliance architecture, age-gating, content moderation tools, and CSAM detection are there precisely so that operators in stable legal environments can run a lawful service. If you are in a country with a functioning rule of law and independent judiciary, the operational security sections of this document are not aimed at you — and using them to evade legitimate legal accountability is not what this software is for.

The line between "authoritarian suppression" and "legitimate law enforcement" is not always clean, and reasonable people disagree on where it falls in specific cases. That judgement is yours to make. What this document does is provide the tools; what you do with them is your responsibility.

---

## The most important thing: full-disk encryption

**No software-level wipe is reliable on modern hardware without full-disk encryption.**

SSDs use wear levelling, TRIM, and firmware-managed write buffering. When you delete a file — even with `shred` — the drive firmware may not overwrite the same physical cells. Data can survive in unaddressed cells indefinitely and may be recoverable with forensic tools.

**The only reliable protection is to never write unencrypted data to disk in the first place.**

### Linux: LUKS (recommended)

Set up LUKS full-disk encryption during OS installation. Most Linux distributions (Ubuntu, Debian, Fedora) offer this during the installer — look for "Encrypt disk" or "LVM with encryption". Choose a strong passphrase.

Full-disk encryption is worth doing regardless of what you run on a machine — anyone setting up a computer today should consider it as basic protection against theft.

With LUKS:
- A powered-off encrypted machine is forensically opaque without the passphrase
- "Wiping" the machine means destroying or forgetting the LUKS header (512 bytes) — instant and irrecoverable

### VeraCrypt (cross-platform alternative)

VeraCrypt supports hidden volumes — a plausible-deniability feature where a second encrypted volume is hidden inside the first. Under coercion you reveal the outer passphrase, which shows innocent data. The hidden volume containing FaceChan is undetectable.

---

## Tor hidden service security

### Your .onion address is your identity

The private key for your `.onion` address lives on disk. If seized, it proves you operated that hidden service. Without LUKS, shredding is not guaranteed on SSDs — another reason full-disk encryption is essential.

### Tor configuration hardening

Add the following to your `torrc`:

```
# Prevent Tor from writing unnecessary data
AvoidDiskWrites 1

# Do not log anything
Log notice stderr
SafeLogging 1

# Restrict hidden service to v3 only
HiddenServiceVersion 3
```

### Never access your .onion from a non-Tor browser

Even once. Correlation attacks can deanonymise you from a single cleartext request.

### First boot: getting your .onion address

A Tor instance requires two boots on initial setup. This is expected and normal — the onion address does not exist until Tor generates it on first run.

**Step 1 — generate your onion address:**

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY and POSTGRES_PASSWORD at minimum
# Leave FEDERATION_BASE_URL unset for now

docker compose -f docker-compose.prod.yml -p facechan-prod up -d --build
```

Wait 30–60 seconds for Tor to initialise, then:

```bash
docker compose -f docker-compose.prod.yml -p facechan-prod logs tor | grep "onion"
```

You will see something like:

```
tor  | [notice] Hostname: abc123youronionaddress.onion
```

That is your permanent address. It will not change as long as you keep the `tor_keys` Docker volume intact.

**Step 2 — configure and restart:**

```bash
# Stop the stack
docker compose -f docker-compose.prod.yml -p facechan-prod down

# Add your onion address to .env
echo "FEDERATION_BASE_URL=http://abc123youronionaddress.onion" >> .env

# Restart — federation is now active
docker compose -f docker-compose.prod.yml -p facechan-prod up -d
```

No rebuild needed for the second start — only the environment variable is changing.

**What happens if you skip Step 2:**

The instance runs perfectly without `FEDERATION_BASE_URL`. Local operation is completely unaffected. Federation is simply inactive — no activities are sent or accepted, and your instance does not appear in discovery endpoints. A warning appears in the Django logs and in the federation dashboard at `/mod/federation` to remind you. You can set it at any time and restart without losing any data.

**Back up your onion keys before anything else:**

```bash
# List the volume location
docker volume inspect facechan-prod_tor_keys

# Back up to a LUKS-encrypted external drive — adapt path as needed
docker run --rm -v facechan-prod_tor_keys:/keys -v /mnt/backup:/backup \
  alpine tar czf /backup/tor_keys_$(date +%Y%m%d).tar.gz -C /keys .
```

Lose the `tor_keys` volume and your onion address is gone permanently — along with your federation identity and any followers.

---

## Network security

### Firewall rules

Your server should accept **only**:
- Tor traffic (Tor manages its own ports internally)
- SSH on a non-standard port if remote management is needed
- Nothing else

```bash
# Example ufw rules for onion-only deployment
ufw default deny incoming
ufw default allow outgoing
ufw allow <your-ssh-port>/tcp
ufw enable
```

### No clearnet exposure

For onion-only deployments, ensure nginx is not listening on any public interface. Bind it to `127.0.0.1` only and let Tor route traffic to it.

Verify:
```bash
ss -tlnp | grep :80
# Should show 127.0.0.1:80 — not 0.0.0.0:80
```

### Running a VPN on the host

If the host machine runs a commercial VPN with a kill switch (NordVPN,
ProtonVPN, Mullvad, etc.), be aware it will block traffic to Docker's bridge
networks by default. The symptom is that the host cannot reach the containers
at all — the dashboard is unreachable from a local browser, `curl localhost`
to the mapped port times out, and `ping` to a container IP shows 100% packet
loss — even though the containers can reach each other internally and the Tor
hidden service may still be working.

This happens because the VPN treats Docker subnets (172.16.0.0/12, commonly
172.18.x.x / 172.19.x.x) as traffic outside the tunnel and drops it. Editing
iptables/UFW rules will not help — the VPN reasserts its own rules.

Allowlist the Docker subnets in the VPN client. For NordVPN:
```bash
nordvpn allowlist add subnet 172.16.0.0/12
```
(Older NordVPN versions call this `whitelist`.) Other clients have an
equivalent "allow LAN / local traffic" toggle or split-tunnel allow list.

Note: federation delivery between instances over Tor is container-to-container
and does not traverse the host→container hop, so onion-to-onion federation can
still function even when this issue blocks host-level access. It primarily
affects operator access to the dashboard and any clearnet binding.

### SSH hardening

```
# /etc/ssh/sshd_config
PasswordAuthentication no
PermitRootLogin no
Port <non-standard port>
```

Use SSH keys only. Consider accessing the server only via SSH over Tor (`torsocks ssh ...`).

---

## Operational security (OpSec)

These are non-technical but equally important:

- **Never access your server from your home network without Tor**
- **Never discuss operating the service on accounts linked to your real identity**
- **Use a dedicated device for server management if possible**
- **Do not reuse passwords or SSH keys between this and personal accounts**
- **The server's purchase/payment trail matters** — pay with Monero or cash if possible; avoid credit cards linked to your identity
- **VPS providers log and can be compelled** — bare metal you physically control is safer for very high-risk deployments
- **Consider your physical environment** — who can see your screen, who knows you run this

---

## Data minimisation

FaceChan logs poster IP addresses. In a high-risk deployment, consider:

- Setting your nginx and Django log level to minimum
- Configuring log rotation with short retention (1–3 days)
- Reviewing `SiteSettings` — rate limits and moderation features reduce abuse without needing to retain logs

The less data you hold, the less there is to find.

---

## ActivityPub federation

See [DEPLOYMENT_FEDERATION.md](DEPLOYMENT_FEDERATION.md) for the full federation guide — how the allowlist works, what federates, legal exposure, finding other instances, and testing.

This section covers the onion-specific differences only.

---

### Setting `FEDERATION_BASE_URL` on an onion instance

Use `http://` not `https://` — Tor provides transport encryption natively:

```
FEDERATION_BASE_URL=http://youronionaddress.onion
```

Your onion address is not known until after first boot — the instance runs fine without `FEDERATION_BASE_URL` set and federation activates automatically once you add it and restart.

### Also add your onion address to `ALLOWED_HOSTS`

This is easy to miss and causes a confusing failure if skipped: Nginx preserves the real `Host` header on every request (required for federation/ActivityPub to work correctly), so Django sees the actual onion hostname, not `localhost`. If your onion address isn't in `ALLOWED_HOSTS`, every request — including login — fails with a generic `400 Bad Request` and no useful error message in the browser.

```
ALLOWED_HOSTS=localhost,127.0.0.1,youronionaddress.onion
```

Do this at the same time as setting `FEDERATION_BASE_URL`, since you'll have the onion address on hand either way, and restart once for both changes.

### Outbound federation over Tor

For your instance to deliver activities to other `.onion` instances, outbound HTTP to `.onion` addresses must route through Tor. The provided Docker Compose includes a dedicated outbound Tor container (`tor-proxy`) on the internal network for exactly this — separate from the inbound hidden-service container.

```
# Already set to the bundled tor-proxy container by default:
FEDERATION_SOCKS_PROXY=socks5h://tor-proxy:9050
```

Only `.onion` destinations are routed through Tor. Clearnet federation connects directly. Set `FEDERATION_SOCKS_PROXY` to an empty string to disable onion outbound entirely.

### Onion-to-onion federation

A network of FaceChan onion instances federating with each other is genuinely censorship-resistant in a way no clearnet network can match. If a node goes down, the others continue. The address cannot be seized or transferred.

### Your .onion address is your federation identity

Your `.onion` address is generated from a private key stored on disk. Lose or destroy that key and remote instances that followed you can no longer reach your Actor URLs — there is no recovery. Back up the `tor_keys` volume or accept that loss of the machine ends your federation relationships.

---

## Summary checklist for high-risk operators

- [ ] Full-disk encryption (LUKS) enabled on the host machine
- [ ] Strong LUKS passphrase — not stored anywhere on the machine
- [ ] Full-disk encryption (LUKS) confirmed active
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
- [ ] If onion-only: understood that destroying Tor keys permanently ends federation relationships

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
