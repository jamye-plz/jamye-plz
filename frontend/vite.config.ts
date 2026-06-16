import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

// TODO(oma-deferred): @vite-pwa/sveltekit(^1.1.0)가 vite 8(rolldown) 빌드의 closeBundle 훅에서
// "Cannot read properties of undefined (reading 'promise')"로 실패한다. 후속 PR에서
// vite 7로 정렬하거나 vite-pwa의 vite 8 지원 버전으로 올린 뒤 SvelteKitPWA 플러그인을
// 재활성화한다(manifest/injectManifest/service-worker.ts 포함). 현재는 PWA 미빌드.

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			// Forward API + WebSocket to the FastAPI backend during dev so the
			// httpOnly auth cookie stays same-origin (localhost:5173).
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true,
				ws: true
			}
		}
	}
});
