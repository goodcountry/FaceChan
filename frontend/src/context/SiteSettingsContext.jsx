import { createContext, useContext, useEffect, useState } from 'react'

const DEFAULT_SETTINGS = {
  site_name: 'FaceChan',
  site_tagline: 'Anonymous-first community platform',
  registration_open: true,
  allow_image_uploads: true,
  max_image_size_mb: 8,
  max_post_length: 5000,
  max_posts_per_thread: 500,
  enable_nsfw_boards: true,
  enable_content_reporting: true,
  require_age_confirmation: true,
  block_nsfw_without_age_gate: true,
  minimum_age: 18,
  publish_transparency_info: true,
  jurisdiction_mode: 'uk',
  moderation_contact: '',
  allow_markdown: true,
  allow_post_editing: false,
  post_edit_window_seconds: 90,
  enable_communities: true,
  allow_avatars: false,
  max_avatar_size_kb: 512,
  mcaptcha_enabled: false,
  mcaptcha_url: '',
  mcaptcha_site_key: '',
}

const SiteSettingsContext = createContext(DEFAULT_SETTINGS)

export function SiteSettingsProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)

  useEffect(() => {
    fetch('/api/site-settings/')
      .then(r => r.json())
      .then(data => {
        setSettings(data)
        // Keep the browser tab title in sync
        document.title = data.site_name || 'FaceChan'
      })
      .catch(() => {
        // API unreachable — fall back to defaults silently
      })
  }, [])

  return (
    <SiteSettingsContext.Provider value={settings}>
      {children}
    </SiteSettingsContext.Provider>
  )
}

export function useSiteSettings() {
  return useContext(SiteSettingsContext)
}
