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

// The browser can invalidate/rotate a push subscription at any time (key
// rotation, expiry). Re-subscribe with the same applicationServerKey and
// hand the new subscription to the backend so future pushes still land.
self.addEventListener('pushsubscriptionchange', (event) => {
	const applicationServerKey = event.oldSubscription?.options.applicationServerKey;
	event.waitUntil(
		self.registration.pushManager
			.subscribe({
				userVisibleOnly: true,
				applicationServerKey
			})
			.then((sub) => {
				const raw = sub.toJSON();
				const keys = raw.keys as { p256dh: string; auth: string };
				return fetch('/api/push/subscribe', {
					method: 'POST',
					credentials: 'include',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						endpoint: sub.endpoint,
						p256dh: keys.p256dh,
						auth: keys.auth
					})
				});
			})
	);
});
