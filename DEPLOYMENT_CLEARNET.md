# FaceChan — Clearnet Deployment Guide

> **Choosing your deployment path?** See [DEPLOYMENT.md](DEPLOYMENT.md) first.

This guide covers deploying FaceChan on a VPS (Virtual Private Server) accessible over the public internet, with a real domain name and HTTPS. It also includes notes for operators who prefer a Platform-as-a-Service (PaaS) approach.

---

## Who this is for

Operators who:
- Want their instance accessible to anyone without requiring Tor Browser
- Are comfortable with their hosting identity being known (to their VPS provider at minimum)
- Are in a stable legal jurisdiction and intend to run a lawful service
- Want the widest possible reach and the simplest day-to-day operations

**If you are in a high-risk environment, are concerned about operator anonymity, or face potential legal or personal danger for running a free speech platform — read [DEPLOYMENT_ONION.md](DEPLOYMENT_ONION.md) instead.**

---

## What you need

- A Linux VPS — Ubuntu 22.04 LTS or Debian 12 recommended. 1 vCPU, 2GB RAM, 20GB disk is sufficient to start.
- A domain name — any registrar. Costs roughly $10–15/year. Namecheap, Porkbun, and Cloudflare are all fine.
- SSH access to your server
- Basic comfort with the Linux command line

Recommended VPS providers with good privacy records: Hetzner, Vultr, DigitalOcean, OVH. Pay with a card or PayPal as normal — clearnet deployment does not require anonymous payment.

---

## Server setup

### 1. Initial access and updates

```bash
ssh root@your-server-ip

apt update && apt upgrade -y
apt install -y git curl ufw
```

### 2. Create a non-root user

```bash
adduser facechan
usermod -aG sudo facechan
# Copy your SSH key to the new user
rsync --archive --chown=facechan:facechan ~/.ssh /home/facechan/
```

Log out and back in as `facechan` for all remaining steps.

### 3. Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 4. SSH hardening

Edit `/etc/ssh/sshd_config`:

```
PasswordAuthentication no
PermitRootLogin no
```

```bash
sudo systemctl restart sshd
```

### 5. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker facechan
# Log out and back in for group membership to take effect
```

---

## Domain and TLS

### Point your domain at the server

In your registrar's DNS panel, add an A record:

```
Type: A
Name: @  (or your subdomain)
Value: your-server-ip
TTL: 3600
```

DNS propagation takes up to 48 hours but is usually minutes. Verify with:

```bash
dig yourdomain.tld +short
# Should return your server IP
```

### Install Certbot for Let's Encrypt TLS

```bash
sudo apt install -y certbot python3-certbot-nginx
```

We will run Certbot after nginx is configured below.

---

## Clone and configure FaceChan

```bash
cd ~
git clone https://github.com/goodcountry/FaceChan.git
cd FaceChan
cp .env.example .env
```

Edit `.env` — the minimum required values for a clearnet deployment:

```env
# Django
SECRET_KEY=generate-a-long-random-string-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.tld,www.yourdomain.tld

# Database
POSTGRES_DB=facechan
POSTGRES_USER=facechan
POSTGRES_PASSWORD=choose-a-strong-password

# Redis
REDIS_URL=redis://redis:6379/0

# Federation
FEDERATION_BASE_URL=https://yourdomain.tld

# Media
MEDIA_URL=/media/
```

Generate a SECRET_KEY:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Nginx configuration

FaceChan ships a production nginx config. For clearnet, update it to use your domain.

Edit `nginx/nginx.conf` (or the prod equivalent in your repo) — set `server_name` to your domain:

```nginx
server_name yourdomain.tld www.yourdomain.tld;
```

By default `docker-compose.prod.yml` keeps nginx internal-only (no host port binding) — this is correct for onion deployments and lets multiple onion instances share one machine. Clearnet deployments need nginx reachable from the public internet, so this guide uses `docker-compose.clearnet-port.yml` as an extra `-f` flag on top of the base file — it adds the `80:80` host port binding without modifying the shared prod file.

---

## Start the stack

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.clearnet-port.yml -p facechan-prod up -d --build
```

Verify all containers are running:

```bash
docker compose -f docker-compose.prod.yml -p facechan-prod ps
```

### Run migrations and create superuser

```bash
docker compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py migrate
docker compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py createsuperuser
```

Grant admin privileges:

```bash
docker compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py grant_admin <username>
```

---

## Issue TLS certificate

With the stack running and DNS propagated:

```bash
sudo certbot --nginx -d yourdomain.tld -d www.yourdomain.tld
```

Certbot will automatically update your nginx config to redirect HTTP to HTTPS and add the certificate. Test auto-renewal:

```bash
sudo certbot renew --dry-run
```

Certbot installs a systemd timer that renews automatically — you do not need to do anything further.

---

## Verify the deployment

Visit `https://yourdomain.tld` in a browser. You should see the FaceChan frontend.

Check the admin panel at `https://yourdomain.tld/admin/` — log in with the superuser credentials you created.

Check federation is working:

```bash
curl https://yourdomain.tld/.well-known/webfinger?resource=acct:g@yourdomain.tld
# Should return JSON describing the /g/ board Actor
```

---

## Ongoing operations

### Updating FaceChan

```bash
cd ~/FaceChan
git pull origin main
docker compose -f docker-compose.prod.yml -f docker-compose.clearnet-port.yml -p facechan-prod up -d --build
docker compose -f docker-compose.prod.yml -p facechan-prod exec web python manage.py migrate
```

### Backups

Back up the PostgreSQL database regularly:

```bash
docker compose -f docker-compose.prod.yml -p facechan-prod exec db \
  pg_dump -U facechan facechan > backup_$(date +%Y%m%d).sql
```

Store backups off-server — an S3 bucket, a local machine, or an encrypted external drive.

Back up your `.env` file and store it securely off-server. It contains your secrets — treat it accordingly.

### Logs

```bash
# All containers
docker compose -f docker-compose.prod.yml -p facechan-prod logs -f

# Web only
docker compose -f docker-compose.prod.yml -p facechan-prod logs -f web
```

Set log rotation to avoid filling your disk — Docker's default logging driver rotates by size but configure retention to suit:

```json
// /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### Monitoring

For a small instance, basic monitoring is sufficient:
- `htop` for CPU/RAM
- `df -h` for disk
- `docker compose ps` to verify all containers are running

For production alerting, [UptimeRobot](https://uptimerobot.com) (free tier) can monitor your domain and notify you if it goes down.

---

## Federation

See [DEPLOYMENT_FEDERATION.md](DEPLOYMENT_FEDERATION.md) for the full federation guide.

For a clearnet instance, set `FEDERATION_BASE_URL` to your domain with `https://`:

```
FEDERATION_BASE_URL=https://yourdomain.tld
```

Your domain name is your federation identity. If it expires or is seized, remote instances that followed you can no longer reach your Actor URLs. Keep registration paid and use a registrar with a strong privacy record.

---

## Legal considerations for clearnet operators

Running a clearnet instance makes you identifiable. Your VPS provider knows who you are. Your domain registrar knows who you are. This is normal and expected for a lawful service — but it means your legal obligations are real and enforceable.

Key points:

- **You are the operator.** The author of FaceChan is the author of the software, not the operator of your instance. Your instance, your responsibility.
- **Read COMPLIANCE.md.** The compliance architecture is real. Age-gating, content moderation tools, and CSAM detection scaffolding are there for a reason — use them.
- **Know your jurisdiction.** UK operators should be aware of the Online Safety Act. EU operators should be aware of the DSA. US operators should be aware of Section 230 and its limits. Get legal advice if you are unsure.
- **The federation allowlist matters.** Federated content is content on your server. You are responsible for what you allow in.
- **Have a takedown process.** Know how you will respond to a report of illegal content before it happens, not after.

---

## PaaS deployment (Railway, Render, Fly.io)

If you prefer not to manage a VPS directly, FaceChan can run on any platform that supports Docker containers and environment variables — which covers most modern PaaS providers.

The core principle is identical: the `.env` variables map directly to the platform's secrets/environment configuration. What changes is how you expose the service, manage the database, and handle persistent storage.

**General steps for any PaaS:**

1. Connect your GitHub repo to the platform
2. Set all `.env` variables as platform secrets/environment variables
3. Point the platform at `docker-compose.prod.yml` or configure individual services manually
4. Use the platform's managed PostgreSQL and Redis add-ons rather than the Docker Compose ones
5. For media storage, configure an S3-compatible bucket (AWS S3, Cloudflare R2, Backblaze B2) — local disk is ephemeral on most PaaS platforms
6. Set `FEDERATION_BASE_URL` to the domain the platform assigns you (or a custom domain)

**Platform-specific notes:**

- **Railway** — supports Docker Compose natively; add managed Postgres and Redis from the Railway dashboard; set environment variables in the Variables tab; volumes are persistent but S3 is recommended for media
- **Render** — supports Docker; use Render's managed Postgres; configure environment variables in the dashboard; disk is ephemeral — S3 required for media
- **Fly.io** — supports Docker; has managed Postgres and Redis add-ons; persistent volumes available but S3 recommended at scale

**Important:** most PaaS platforms require a credit card and link your identity to the deployment. This is fine for a lawful clearnet service. It is not appropriate if operator anonymity matters to you — use a VPS or onion deployment instead.

---

## Checklist

- [ ] VPS provisioned, updated, non-root user created
- [ ] Firewall configured (ports 22, 80, 443 only)
- [ ] SSH hardened (keys only, no root login)
- [ ] Docker installed
- [ ] Domain DNS pointing at server IP
- [ ] FaceChan cloned, `.env` configured
- [ ] Stack started with `docker compose -f docker-compose.prod.yml -f docker-compose.clearnet-port.yml -p facechan-prod up -d --build`
- [ ] Migrations run, superuser created, `grant_admin` run
- [ ] TLS certificate issued via Certbot
- [ ] Instance accessible at `https://yourdomain.tld`
- [ ] Federation webfinger endpoint verified
- [ ] Backup process in place
- [ ] Log rotation configured
- [ ] COMPLIANCE.md read and understood
- [ ] Legal obligations for your jurisdiction reviewed

---

*FaceChan is MIT-licensed software. The author is not responsible for your deployment.*
