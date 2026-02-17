/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_RECAPTCHA_SITE_KEY: string
  // adicione outras variáveis VITE_ aqui se necessário
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}


