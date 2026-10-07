import { readdirSync, readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

/**
 * Serve pdf.js's runtime data (image decoders, CMaps, colour profile, standard fonts) under
 * /pdfjs-<version>/. pdf.js fetches these by fixed file name, so they can't go through Vite's
 * hashed asset pipeline; the version in the path stands in for the hash.
 */
function pdfjsData(): Plugin {
  const root = new URL('./node_modules/pdfjs-dist/', import.meta.url)
  const { version } = JSON.parse(readFileSync(new URL('package.json', root), 'utf8')) as { version: string }
  const dirs: Record<string, RegExp> = {
    wasm: /^(jbig2|openjpeg|qcms_bg)\.wasm$|_nowasm_fallback\.js$/,
    cmaps: /\.bcmap$/,
    iccs: /\.icc$/,
    standard_fonts: /\.(pfb|ttf)$/,
  }
  // Allowlist of servable paths, e.g. "wasm/jbig2.wasm", so the dev middleware can't be walked out of these dirs.
  const files = Object.entries(dirs).flatMap(([dir, pattern]) =>
    readdirSync(new URL(dir, root))
      .filter((name) => pattern.test(name))
      .map((name) => `${dir}/${name}`),
  )
  const base = `pdfjs-${version}`
  const contentType = (file: string) =>
    file.endsWith('.js') ? 'text/javascript' : file.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream'

  return {
    name: 'pdfjs-data',
    configureServer(server) {
      server.middlewares.use(`/${base}/`, (req, res, next) => {
        const file = (req.url ?? '').split('?')[0].replace(/^\//, '')
        if (!files.includes(file)) return next()
        res.setHeader('Content-Type', contentType(file))
        res.end(readFileSync(new URL(file, root)))
      })
    },
    generateBundle() {
      for (const file of files) {
        this.emitFile({ type: 'asset', fileName: `${base}/${file}`, source: readFileSync(new URL(file, root)) })
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), pdfjsData()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
