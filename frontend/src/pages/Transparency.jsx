import { useSiteSettings } from '../context/SiteSettingsContext'
import { ShieldCheck, Mail, Scale, Flag } from 'lucide-react'

const JURISDICTION_LABELS = {
  uk: 'United Kingdom (Online Safety Act)',
  eu: 'European Union (Digital Services Act)',
  us: 'United States (Section 230 host)',
  other: 'Operator-defined',
}

export default function Transparency() {
  const settings = useSiteSettings()

  if (settings.publish_transparency_info === false) {
    return (
      <div className="page-layout">
        <div className="page-header">
          <ShieldCheck size={20} className="accent" />
          <h1>Transparency</h1>
        </div>
        <p className="muted">This instance has not published transparency information.</p>
      </div>
    )
  }

  const jurisdictionLabel = JURISDICTION_LABELS[settings.jurisdiction_mode] || 'Not specified'

  return (
    <div className="page-layout">
      <div className="page-header">
        <ShieldCheck size={20} className="accent" />
        <h1>Transparency &amp; Reporting</h1>
      </div>

      <p className="muted">
        This page describes how {settings.site_name || 'this instance'} is operated and how
        to report content or reach the operator. It is published in good faith and is not a
        substitute for any jurisdiction's statutory disclosure requirements.
      </p>

      <div className="transparency-grid">
        <section className="transparency-card">
          <h2><Scale size={16} /> Operating jurisdiction</h2>
          <p>{jurisdictionLabel}</p>
        </section>

        <section className="transparency-card">
          <h2><Flag size={16} /> Content reporting</h2>
          <p>
            {settings.enable_content_reporting
              ? 'Content reporting is enabled. Use the Report control on any thread or post to flag it for moderator review.'
              : 'Content reporting via the in-app report control is currently disabled on this instance.'}
          </p>
        </section>

        <section className="transparency-card">
          <h2><Mail size={16} /> Moderation contact</h2>
          <p>
            {settings.moderation_contact
              ? <a href={`mailto:${settings.moderation_contact}`}>{settings.moderation_contact}</a>
              : 'No public moderation contact has been set for this instance.'}
          </p>
        </section>
      </div>

      <p className="muted transparency-note">
        Reports of child sexual abuse material should always also go to your national
        authority regardless of any instance-level process — the NCA's CSEA reporting portal
        in the UK, or NCMEC's CyberTipline in the US.
      </p>
    </div>
  )
}
