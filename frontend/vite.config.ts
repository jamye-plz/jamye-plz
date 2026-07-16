import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	// Required so the injectManifest service worker (imports workbox-*) registers
	// correctly — see @vite-pwa/sveltekit docs.
	define: {
		'process.env.NODE_ENV':
			process.env.NODE_ENV === 'production' ? '"production"' : '"development"'
	},
	plugins: [
		tailwindcss(),
		sveltekit(),
		SvelteKitPWA({
			strategies: 'injectManifest',
			srcDir: 'src',
			filename: 'service-worker.ts',
			registerType: 'autoUpdate',
			injectRegister: 'auto',
			manifest: {
				name: '잼얘좀',
				short_name: '잼얘좀',
				description: '재밌는 얘기 좀 해봐',
				lang: 'ko',
				theme_color: '#ffffff',
				background_color: '#ffffff',
				display: 'standalone',
				start_url: '/',
				icons: [
					{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
					{
						src: '/icons/icon-512.png',
						sizes: '512x512',
						type: 'image/png',
						purpose: 'maskable'
					}
				]
			},
			injectManifest: {
				globPatterns: ['client/**/*.{js,css,ico,png,svg,webp,woff,woff2}'],
				// adapter-static writes the SPA fallback (index.html) after Vite PWA's
				// scan, so precache it explicitly (fetched at SW install). New revision
				// per build busts the cached shell on each deploy.
				additionalManifestEntries: [{ url: '/index.html', revision: `build-${Date.now()}` }]
			},
			// Keep the dev server free of the SW; test PWA via `bun run preview`.
			devOptions: {
				enabled: false
			}
		})
	],
	server: {
		// Allow tunnel hosts (localtunnel / cloudflared / ngrok) for mobile testing.
		allowedHosts: ['.loca.lt', '.trycloudflare.com', '.ngrok-free.app', '.ngrok.io'],
		proxy: {
			// Forward API + WebSocket to the FastAPI backend during dev so the
			// httpOnly auth cookie stays same-origin (localhost:5173).
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				ws: true
			}
		}
	},
	preview: {
		allowedHosts: ['.loca.lt', '.trycloudflare.com', '.ngrok-free.app', '.ngrok.io']
	}
});
