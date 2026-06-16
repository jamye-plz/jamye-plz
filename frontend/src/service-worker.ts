/// <reference types="@vite-pwa/sveltekit/dist/worker" />
/// <reference lib="webworker" />

import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching';

declare let self: ServiceWorkerGlobalScope;

// Precache all static assets injected by Vite PWA
precacheAndRoute(self.__WB_MANIFEST);

// Clean up old caches when SW is activated
cleanupOutdatedCaches();

self.addEventListener('activate', (event) => {
	event.waitUntil(self.clients.claim());
});

// TODO: Add push notification handling when backend VAPID is provisioned
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
		self.clients
			.matchAll({ type: 'window' })
			.then((clients) => {
				const client = clients.find((c) => c.url === url && 'focus' in c);
				if (client) return client.focus();
				return self.clients.openWindow(url);
			})
	);
});
