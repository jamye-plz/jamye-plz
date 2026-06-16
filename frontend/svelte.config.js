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
		alias: {
			$lib: './src/lib'
		}
	}
};

export default config;
