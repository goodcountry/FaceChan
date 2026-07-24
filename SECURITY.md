# Security

Found a vulnerability? Thank you. Here's how to reach me — including how to do it without telling me who you are.

## Contact

**Email:** `kinofacechan@proton.me`

**PGP key:** [`pgp.asc`](./pgp.asc) in this repository.

```
Fingerprint: B3BF 5E7F 9205 2C90 88DF  7E4F FCFC 5EFD DAE5 8505
Kino <kinofacechan@proton.me>
```

This is the same key that signs every merge to `main`, so you can verify you have the real contact key by checking the repository's commit signatures — an attacker who swapped this file would break the signed history.

```bash
gpg --import pgp.asc
git log --show-signature --merges -5
```

## Reporting anonymously

You don't need to identify yourself to report a vulnerability. Some honest notes if you care about that:

- **A throwaway address is fine.** Proton Mail accepts signups over Tor. Mail between Proton accounts is end-to-end encrypted automatically, no PGP setup needed.
- **From any other provider, encrypt to the key above.** PGP encrypts the message body — but not the metadata. Your provider still sees who you emailed and when. If that matters to you, use a burner address created over Tor, not your real one with encryption bolted on.
- **GitHub private vulnerability reporting** is enabled on this repository as a low-friction alternative. Be aware it requires a GitHub account, so it's pseudonymous at best, not anonymous.
- **Credit is yours to take or leave.** Tell me how you want to be credited, or that you don't. Default is uncredited.

## What to include

Whatever you'd want if you were fixing it: affected component, how to reproduce, impact as you understand it. A proof of concept helps but isn't required. Don't test against instances you don't operate — spin up your own; it's self-hostable for a reason.

## What to expect

I'm one person, not a security team. I read reports and I take them seriously, but there's no SLA, no bug bounty, and no legal department to send you a safe-harbour letter. What I can promise: I won't pursue anyone who reports in good faith, and fixes ship as fast as I can write them.

If a vulnerability affects instance operators, the fix lands in `main` with a clear commit message and a note in the relevant deployment doc. Operators should watch the repository for updates — see [Fork it, don't just download it](./README.md#fork-it-dont-just-download-it).

## Scope

FaceChan the codebase. Individual instances are run by their own operators — if you find a problem with a specific instance's deployment (misconfiguration, exposed services), contact that instance's `moderation_contact`, listed on its transparency page.
