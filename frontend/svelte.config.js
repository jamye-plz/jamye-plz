import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		adapter: adapter({
			// SPA fallback: all paths serve index.html
			fallback: 'index.html'
		}),
		// Let @vite-pwa/sveltekit own the service worker instead of SvelteKit's
		// built-in registration (our SW uses workbox's __WB_MANIFEST).
		serviceWorker: {
			register: false
		},
		alias: {
			$lib: './src/lib'
		}
	}
};

export default config;
