# Illegal Content & Safety Risk Assessment — Template

A starting template for operators of a FaceChan instance. It is modelled loosely on
the kind of risk assessment Ofcom expects from smaller user-to-user services under
the UK Online Safety Act, but it is generic enough to adapt to other regimes.

**This is not legal advice and not a guarantee of compliance.** It is a structure to
help you think through and document your own assessment. Operators in other
jurisdictions should adapt it to their own law.

Fill it in, date it, keep it, and review it whenever your instance changes
materially.

---

## 1. Instance details

- Instance name / onion or domain:
- Operator (individual or company):
- Jurisdiction(s) you consider yourself subject to:
- Date of this assessment:
- Date of next planned review:

## 2. Service description

- What is your instance for? Who is it aimed at?
- Roughly how many users? Are any likely to be children?
- Is it clearnet, Tor, or both?
- Is registration open, invite-only, or closed?

## 3. Risk identification

For each category, note the likelihood and how it could appear on your instance:

- Child sexual abuse material (CSAM)
- Terrorism / violent extremism content
- Illegal hate speech / harassment
- Threats, intimidation, stalking
- Fraud / scams
- Sale of illegal goods (drugs, weapons)
- Self-harm / suicide promotion
- Intimate image abuse
- Other illegal content relevant to your jurisdiction

## 4. Existing controls

Note which FaceChan controls you have enabled and any external measures:

- [ ] CSAM protections (permanent floor — always on)
- [ ] Content reporting enabled (`enable_content_reporting`)
- [ ] Age confirmation (`require_age_confirmation`, `minimum_age`)
- [ ] NSFW age-gating (`block_nsfw_without_age_gate`)
- [ ] Transparency info published (`publish_transparency_info`)
- [ ] Moderation contact set (`moderation_contact`)
- [ ] Active moderation / mod queue monitoring
- [ ] Registration restrictions (invite-only, etc.)
- [ ] Logging / records retention policy
- [ ] External reporting registrations (NCA portal, NCMEC, etc.)

## 5. Residual risk & further measures

- After existing controls, where does meaningful risk remain?
- What proportionate further measures will you take, and by when?

## 6. Sign-off

- Assessed by:
- Date:
- Review due:

---

*Part of the FaceChan project. Adapt to your jurisdiction. Not legal advice.*
