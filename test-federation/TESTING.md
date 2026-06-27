# Federation Test — Two Local Onion Instances

Two full FaceChan stacks running on the same Linux Mint machine, each with its
own Tor hidden service, federating with each other over Tor exactly as two
real-world instances would.

---

## Prerequisites

- Docker + Docker Compose installed on Linux Mint
- Tor Browser installed (for browsing the onion sites during testing)
- The repo cloned somewhere, e.g. `~/FaceChan`

---

## Step 1 — Prepare .env files

```bash
cd ~/FaceChan

cp test-federation/instance-a/.env.example test-federation/instance-a/.env
cp test-federation/instance-b/.env.example test-federation/instance-b/.env
```

Edit each `.env` — at minimum set unique values for:
- `SECRET_KEY` — any long random string (different for each instance)
- `POSTGRES_PASSWORD` — any password (different for each instance)

Leave `FEDERATION_BASE_URL` and `ALLOWED_HOSTS` blank for now — you'll fill
them in after first boot once you have the onion addresses.

---

## Step 2 — First boot (get onion addresses)

Start both instances **without** `FEDERATION_BASE_URL` set. They'll start in
graceful unconfigured mode — fully functional locally, federation delivery
disabled until the URL is set.

```bash
# From repo root
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a up -d --build
docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b up -d --build
```

Wait ~60 seconds for first boot (migrations + static files + Tor circuit).

Get the onion addresses:

```bash
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a logs tor 2>&1 | grep -i "hostname\|onion"
docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b logs tor 2>&1 | grep -i "hostname\|onion"
```

If the above doesn't show it, read directly from the Tor volume:

```bash
docker run --rm -v fc-a_tor_keys:/data alpine cat /data/hostname
docker run --rm -v fc-b_tor_keys:/data alpine cat /data/hostname
```

Note both addresses — e.g.:
- Instance A: `aaa111bbb222ccc333.onion`
- Instance B: `ddd444eee555fff666.onion`

---

## Step 3 — Set federation URLs and restart

Edit `test-federation/instance-a/.env`:
```
FEDERATION_BASE_URL=http://aaa111bbb222ccc333.onion
ALLOWED_HOSTS=localhost,127.0.0.1,aaa111bbb222ccc333.onion
```

Edit `test-federation/instance-b/.env`:
```
FEDERATION_BASE_URL=http://ddd444eee555fff666.onion
ALLOWED_HOSTS=localhost,127.0.0.1,ddd444eee555fff666.onion
```

Restart both (no rebuild needed — just picks up the new env):

```bash
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a up -d
docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b up -d
```

---

## Step 4 — Create admin accounts and grant dashboard access

A Django superuser alone is **not** enough to access the federation dashboard.
The dashboard requires an admin-tier Role with content-purge permission.
Run both commands for each instance.

**Instance A:**
```bash
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a \
  exec web python manage.py createsuperuser

docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a \
  exec web python manage.py grant_admin <username>
```

**Instance B:**
```bash
docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b \
  exec web python manage.py createsuperuser

docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b \
  exec web python manage.py grant_admin <username>
```

Replace `<username>` with the superuser name you chose.

---

## Step 5 — Create at least one local board on each instance

The federation dashboard lets you map *remote* boards to *local* boards.
If an instance has no local boards yet, there is nothing to map to and
inbound federated threads will be silently rejected.

```bash
# Django shell on Instance A
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a \
  exec web python manage.py shell
```

```python
from boards.models import Board
Board.objects.create(slug="tech", name="Technology", allow_federation=True)
exit()
```

Repeat for Instance B (same slug is fine — they're separate databases).

Alternatively create boards through the moderation UI at
`http://localhost:8101/mod/` once host access is confirmed working.

---

## Step 6 — Wire up federation (two-way)

Federation is **directional**: each instance must independently add and approve
the other, then set up its own board mapping. Do the full sequence on A first,
then repeat on B.

**Via Tor Browser (recommended — tests the real delivery path):**

**On Instance A** (`http://aaa111bbb222ccc333.onion/mod/federation`):

1. Open Tor Browser and go to Instance A's federation dashboard
2. Log in as the admin user
3. Under "Add remote instance", paste `http://ddd444eee555fff666.onion` and submit
4. The new instance will appear with status *pending* — click Approve
5. After approval Instance A auto-fetches Instance B's board list (Celery task)
6. Once the board list appears, use the mapping dropdown to map a remote board
   to one of A's local boards and save

**On Instance B** (`http://ddd444eee555fff666.onion/mod/federation`):

7. Repeat steps 1–6 in the other direction: add A's onion address, approve it,
   wait for board fetch, create a mapping

When a mapping is saved (or updated), the instance automatically sends a
Follow activity to the remote board. The remote instance auto-accepts it and
sends an Accept back. Both directions need to be set up for bidirectional
thread delivery.

**Alternatively via the host HTTP port (faster for initial setup):**

Instance A is reachable at `http://localhost:8101` and B at `http://localhost:8102`
without Tor Browser — useful for setup steps where you don't need to test the
real onion delivery path. Remember the NordVPN caveat in Troubleshooting if
the host port is unreachable.

---

## Step 7 — Test scenarios

### Threads
1. On Instance A: log in, go to a federated board, post a thread
2. On Instance B: open the mapped board — the thread should appear within
   a few seconds (Celery delivers it, BoardConsumer pushes via WebSocket)

### Replies
1. On Instance B: log in, reply to the federated thread that arrived from A
2. On Instance A: the reply should appear in the thread view

### Inbound without a page refresh
1. Keep Instance B's board view open in Tor Browser
2. Post a thread on Instance A
3. Watch it appear on Instance B without refreshing — that's the WebSocket listener

### Anonymous posts
1. Post a thread anonymously on Instance A (log out first)
2. Verify it does NOT appear on Instance B — anonymous posts stay local

---

## Useful commands

```bash
# Tail all logs for Instance A
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a logs -f

# Tail just the Celery worker (delivery attempts)
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a logs -f celery

# Django shell on Instance A
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a \
  exec web python manage.py shell

# Check FederationActivity log (in Django shell)
# from federation.models import FederationActivity
# FederationActivity.objects.order_by('-created_at')[:10].values('direction','activity_type','status','error')

# Stop everything
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a down
docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b down

# Full teardown including volumes (wipes databases and onion keys)
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a down -v
docker-compose -f test-federation/instance-b/docker-compose.yml -p fc-b down -v
```

---

## Troubleshooting

**Browser/curl to `localhost:8101` hangs and times out (VPN running)**

If you cannot reach the instance from the host at all — `curl http://localhost:8101/`
times out, the browser spins forever, and even `ping <container-ip>` shows 100%
packet loss — but the containers can reach *each other* internally, the cause is
almost certainly a **VPN with a kill switch** (NordVPN, ProtonVPN, Mullvad, etc.)
running on the host.

These VPNs install firewall rules that drop any traffic outside the VPN tunnel.
Docker's bridge networks (172.18.x.x / 172.19.x.x) count as "outside the tunnel",
so return packets from containers are silently dropped. The give-away signature:

- Containers talk to each other fine (`docker exec ... ping <other-container-ip>` works)
- Host reaches the bridge *gateway* (`ping 172.18.0.1` works)
- Host CANNOT reach container IPs or mapped ports (`ping 172.18.0.8`, `curl localhost:8101` both fail)
- Editing iptables/UFW rules has no effect (the VPN reasserts its own)

**Fix (NordVPN):** either disconnect the VPN while testing —
```bash
nordvpn disconnect
```
— or, to keep the VPN connected, allowlist the Docker bridge subnets permanently:
```bash
nordvpn allowlist add subnet 172.18.0.0/16
nordvpn allowlist add subnet 172.19.0.0/16
```
(Older NordVPN versions call this `whitelist` instead of `allowlist`.)

For other VPNs the equivalent is enabling "allow LAN / local network traffic" in
the client settings, or adding the same two subnets to its split-tunnel/allow list.

Note: the Tor onion federation path is container-to-container and never makes the
host→container hop, so onion delivery between instances can work even while this
host-access problem is present. The host-access issue only blocks *you* reaching
the dashboard from a browser on the host.

**Tor address not showing in logs**

The `goldy/tor-hidden-service` image writes the hostname to a volume, not
always to stdout. Use the `docker run` volume-read command in Step 2.

**Federation dashboard shows "Federation not configured"**

`FEDERATION_BASE_URL` is not set or is still `localhost`. Set it to the full
onion address (including `http://`) and restart the web container.

**Threads not arriving on the remote instance**

Check the Celery logs — delivery errors will show there. Common causes:
- Tor circuit not yet established (wait another 30s and retry)
- `ALLOWED_HOSTS` on the receiving instance doesn't include the onion address
- Board mapping not set up on the receiving instance

**`FederationActivity` status is `failed`**

Run the Django shell command above to inspect the `error` field — it will
contain the HTTP status code or connection error from the delivery attempt.

**Port conflict on 8101 or 8102**

Change the host port in the relevant `docker-compose.yml` (left side of the
`ports:` mapping) to any free port.

**Outbound delivery fails — `.onion` address unreachable**

Each instance needs **two** Tor-related containers:

| Container | Role |
|-----------|------|
| `tor` | Inbound hidden service — makes this instance reachable as an `.onion` |
| `tor-proxy` | Outbound SOCKS proxy — lets Django reach *other* `.onion` addresses |

If `tor-proxy` is missing or its port (9050) is unreachable from the `web`
container, all outbound AP delivery to `.onion` remotes will fail with a
connection error. Check that both containers are running:

```bash
docker-compose -f test-federation/instance-a/docker-compose.yml -p fc-a ps
```

You should see `fc-a_tor_1` and `fc-a_tor-proxy_1` both Up.

The `FEDERATION_SOCKS_PROXY` env var must be set to `socks5h://tor-proxy:9050`
(already set in `.env.example`). The `socks5h` scheme tells the SOCKS client
to resolve the hostname through the proxy — required for `.onion` addresses.

**WebSocket reconnect loop / Redis timeout errors in logs**

If the Celery or web logs show repeated lines like:

```
Error reading from channel layer: Timeout reading from redis:6379
```

…and the browser console shows the board WebSocket reconnecting every ~11
seconds, the channel layer is misconfigured. The default `RedisChannelLayer`
uses blocking-pop which times out on idle connections and closes the consumer.

The correct layer is `RedisPubSubChannelLayer` (same `channels_redis` package,
no extra dependency). In `settings.py`:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
        "CONFIG": {"hosts": [("redis", 6379)]},
    }
}
```

This is already set correctly in the test compose `.env.example` — if you see
this error in a fresh stack, check that your `.env` hasn't overridden it.
