/**
 * CaptchaField
 *
 * Renders two things:
 * 1. A honeypot `website` field — hidden off-screen, never filled by humans.
 * 2. An mCaptcha widget — only when mcaptcha_enabled is true in site settings.
 *
 * Usage:
 *   <CaptchaField onChange={token => setMcaptchaToken(token)} />
 *
 * Include `website` and (if configured) `mcaptcha_token` in your form data.
 * The honeypot value should always be '' — the parent never sets it.
 */
import { useEffect, useRef } from 'react'
import { useSiteSettings } from '../context/SiteSettingsContext'

export default function CaptchaField({ onChange }) {
  const { mcaptcha_enabled, mcaptcha_url, mcaptcha_site_key } = useSiteSettings()
  const widgetRef = useRef(null)

  useEffect(() => {
    if (!mcaptcha_enabled || !mcaptcha_url || !mcaptcha_site_key) return
    if (!widgetRef.current) return

    // Load mCaptcha widget script dynamically
    const scriptId = 'mcaptcha-script'
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script')
      script.id = scriptId
      script.src = `${mcaptcha_url.replace(/\/$/, '')}/widget.js`
      script.async = true
      document.head.appendChild(script)
    }

    // mCaptcha fires a custom event with the token on success
    const handler = e => {
      if (onChange) onChange(e.detail?.token || '')
    }
    window.addEventListener('mcaptcha-token', handler)
    return () => window.removeEventListener('mcaptcha-token', handler)
  }, [mcaptcha_enabled, mcaptcha_url, mcaptcha_site_key, onChange])

  return (
    <>
      {/* Honeypot — hidden off-screen, not display:none (bots see through that) */}
      <div style={{
        position: 'absolute',
        left: '-9999px',
        top: '-9999px',
        width: '1px',
        height: '1px',
        overflow: 'hidden',
        opacity: 0,
        pointerEvents: 'none',
        tabIndex: -1,
        ariaHidden: 'true',
      }}>
        <label htmlFor="website">Website</label>
        <input
          type="text"
          id="website"
          name="website"
          autoComplete="off"
          tabIndex={-1}
        />
      </div>

      {/* mCaptcha widget — only rendered when configured */}
      {mcaptcha_enabled && mcaptcha_url && mcaptcha_site_key && (
        <div
          ref={widgetRef}
          className="mcaptcha-widget"
          data-sitekey={mcaptcha_site_key}
          data-mcaptcha-url={mcaptcha_url}
          style={{ marginTop: '8px' }}
        />
      )}
    </>
  )
}
