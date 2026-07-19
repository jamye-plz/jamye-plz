/// <reference types="@vite-pwa/sveltekit/dist/worker" />
/// <reference lib="webworker" />

import {
	cleanupOutdatedCaches,
	createHandlerBoundToURL,
	precacheAndRoute
} from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';

declare let self: ServiceWorkerGlobalScope;

// __WB_MANIFEST is injected exactly once by Vite PWA; capture it before reuse.
const manifest = self.__WB_MANIFEST;

// Precache all static assets injected by Vite PWA
precacheAndRoute(manifest);

// Clean up old caches when SW is activated
cleanupOutdatedCaches();

// SPA navigation fallback: serve the precached app shell for any navigation
// (offline launches, deep links like /groups/...). Only registered when the
// fallback document was actually precached, so SW install never fails.
if (manifest.some((e) => (typeof e === 'string' ? e : e.url).endsWith('/index.html'))) {
	registerRoute(
		new NavigationRoute(createHandlerBoundToURL('/index.html'), {
			// Backend navigations (OAuth callbacks, etc.) must hit the network,
			// not the cached app shell — otherwise the auth cookie is never set.
			denylist: [/^\/api\//]
		})
	);
}

self.addEventListener('activate', (event) => {
	event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
	if (!event.data) return;
	const data = event.data.json() as { title: string; body: string; url?: string };
	event.waitUntil(
		self.registration.showNotification(data.title, {
			body: data.body,
			icon: '/icons/icon-192.png',
			badge: '/icons/icon-192.png',
			data: { url: data.url ?? '/' }
		})
	);
});

self.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const url = (event.notification.data as { url: string }).url;
	event.waitUntil(
		self.clients.matchAll({ type: 'window' }).then((clients) => {
			const client = clients.find((c) => c.url === url && 'focus' in c);
			if (client) return client.focus();
			return self.clients.openWindow(url);
		})
	);
});

function base64urlToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
	const padding = '='.repeat((4 - (base64.length % 4)) % 4);
	const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
	const out = new Uint8Array(new ArrayBuffer(raw.length));
	for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
	return out;
}

// The browser can invalidate/rotate a push subscription at any time (key
// rotation, expiry). Re-subscribe with the CURRENT server VAPID key — fetched
// fresh, not `oldSubscription`'s key, which may be stale after a server-side
// rotation (a subscription bound to the old public key would be rejected by
// the push service once the backend signs with the new private key). Fall back
// to the old key only if the fetch fails.
self.addEventListener('pushsubscriptionchange', (event) => {
	event.waitUntil(
		(async () => {
			let applicationServerKey: BufferSource | undefined =
				event.oldSubscription?.options.applicationServerKey ?? undefined;
			try {
				const res = await fetch('/api/push/vapid-public-key', { credentials: 'include' });
				if (res.ok) {
					const { public_key } = (await res.json()) as { public_key: string };
					if (public_key) applicationServerKey = base64urlToUint8Array(public_key);
				}
			} catch {
				// keep the old key as a best-effort fallback
			}
			if (!applicationServerKey) return;
			const sub = await self.registration.pushManager.subscribe({
				userVisibleOnly: true,
				applicationServerKey
			});
			const keys = sub.toJSON().keys as { p256dh: string; auth: string };
			// If the backend didn't store the new endpoint — whether it responded
			// 401/5xx (`fetch` resolves) OR the request rejected outright
			// (offline/network/CORS) — tear the just-created local subscription
			// back down instead of leaving a live browser subscription with no
			// matching row (which would silently receive nothing). The global
			// reconciler recreates it cleanly the next time the app is opened.
			const registered = await fetch('/api/push/subscribe', {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ endpoint: sub.endpoint, p256dh: keys.p256dh, auth: keys.auth })
			})
				.then((res) => res.ok)
				.catch(() => false);
			if (!registered) await sub.unsubscribe();
		})()
	);
});
