// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-05-04',
  devtools: { enabled: true },

  modules: [
    '@nuxtjs/i18n',
  ],

  runtimeConfig: {
    public: {
      apiBaseUrl: 'http://localhost:8000',
    },
  },

  nitro: {
    devProxy: {
      '/api/': {
        target: (process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000') + '/api/',
        changeOrigin: true,
      },
    },
  },

  i18n: {
    locales: [
      { code: 'nl', language: 'nl-NL', name: 'Nederlands', file: 'nl.json' },
      { code: 'en', language: 'en-GB', name: 'English', file: 'en.json' },
      { code: 'de', language: 'de-DE', name: 'Deutsch', file: 'de.json' },
      { code: 'fr', language: 'fr-FR', name: 'Français', file: 'fr.json' },
    ],
    defaultLocale: 'nl',
    strategy: 'prefix',
    lazy: true,
  },
})
