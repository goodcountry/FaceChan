# FaceChan Instance Directory

A community-maintained list of known FaceChan instances.

**The author of FaceChan does not operate, endorse, or take any responsibility for any instance listed here.** Each instance is independently operated. Content policies, moderation standards, and reliability vary. Use your own judgement before joining or federating.

---

## Listed Instances

| URL | Type | Content policy | Federation | Notes |
|---|---|---|---|---|
| *Be the first to list your instance — see below* | | | | |

---

## Submit Your Instance

Open a pull request adding a row to the table above. Copy the template below, fill it in, and that's it. No approval process beyond basic checks — if your instance is reachable and your entry is honest, it gets listed.

**Template:**

```
| https://your-url-here.tld | Clearnet | Brief content policy | Enabled / Disabled | Any notes |
```

**Field guide:**

- **URL** — your `FEDERATION_BASE_URL`. Clearnet domain or `.onion` address. Onion entries must include the explicit `http://` prefix (e.g. `http://youraddress.onion`) — some browsers, including Tor Browser on Android, silently upgrade schemeless addresses to HTTPS, which fails against http-only onion services.
- **Type** — `Clearnet`, `Onion`, or `Dual-stack`
- **Content policy** — a short honest description. Examples:
  - `General, SFW only`
  - `General, NSFW allowed`
  - `Text only, no images or video`
  - `Tech-focused, SFW`
  - `Adults only, NSFW`
- **Federation** — `Enabled` or `Disabled`
- **Notes** — language, theme, anything relevant. Leave blank if nothing to add.

**Rules:**

1. Your instance must be reachable at the listed URL at the time of submission.
2. Your content policy description must be accurate. Misrepresenting your instance (e.g. listing as SFW when it isn't) is grounds for removal.
3. One entry per instance.
4. The PR author takes responsibility for the accuracy of their submission.

**Removal:** open a PR removing your row, or file an issue if you believe a listed instance is misrepresenting itself.

---

*This directory is a convenience, not a registry. No instance is required to list itself here, and listing here confers no special status. Federation is always at the discretion of each individual operator.*
