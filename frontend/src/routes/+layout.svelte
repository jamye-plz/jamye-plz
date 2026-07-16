<script lang="ts">
	import '../app.css';
	import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/state';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';

	let { children } = $props();

	// Register the PWA service worker (production build only; dev runs SW-free).
	onMount(() => {
		if (import.meta.env.PROD) {
			import('virtual:pwa-register').then(({ registerSW }) => registerSW({ immediate: true }));
		}
	});

	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				staleTime: 1000 * 60 * 5, // 5 minutes
				retry: (failureCount, error: unknown) => {
					// Do not retry on 401/403
					const status = (error as { status?: number })?.status;
					if (status === 401 || status === 403) return false;
					return failureCount < 2;
				}
			}
		}
	});

	onDestroy(() => {
		queryClient.clear();
	});

	// ── Pull-to-refresh (mobile) ───────────────────────────────────────────────
	// Drag down past the top of a page to reload. Enabled on every page EXCEPT the
	// chat room: chat is live over WebSocket and scroll-up already pages in older
	// history, so a reload gesture there would only fight those.
	const PTR_TRIGGER = 64; // px of (resisted) pull needed to fire
	const PTR_MAX = 110;
	let pullY = $state(0);
	let refreshing = $state(false);
	let startY = 0;
	let armed = false;

	// Chat routes own their own scroll; both end in "/chat".
	const isChatRoute = $derived(page.route.id?.endsWith('/chat') ?? false);

	function onTouchStart(e: TouchEvent) {
		armed = false;
		if (refreshing || isChatRoute || e.touches.length !== 1) return;
		const sc = document.scrollingElement ?? document.documentElement;
		if (sc.scrollTop > 0) return;
		startY = e.touches[0].clientY;
		armed = true;
	}

	function onTouchMove(e: TouchEvent) {
		if (!armed || refreshing) return;
		const dy = e.touches[0].clientY - startY;
		if (dy <= 0) {
			pullY = 0;
			return;
		}
		pullY = Math.min(PTR_MAX, dy * 0.5); // resistance
		if (pullY > 0 && e.cancelable) e.preventDefault(); // take over native overscroll
	}

	function onTouchEnd() {
		if (!armed || refreshing) {
			pullY = 0;
			return;
		}
		armed = false;
		if (pullY >= PTR_TRIGGER) {
			refreshing = true;
			pullY = 50;
			// brief paint so the spinner is visible, then reload.
			setTimeout(() => location.reload(), 250);
		} else {
			pullY = 0;
		}
	}

	onMount(() => {
		window.addEventListener('touchstart', onTouchStart, { passive: true });
		window.addEventListener('touchmove', onTouchMove, { passive: false });
		window.addEventListener('touchend', onTouchEnd, { passive: true });
		window.addEventListener('touchcancel', onTouchEnd, { passive: true });
		return () => {
			window.removeEventListener('touchstart', onTouchStart);
			window.removeEventListener('touchmove', onTouchMove);
			window.removeEventListener('touchend', onTouchEnd);
			window.removeEventListener('touchcancel', onTouchEnd);
		};
	});

	const ptrReady = $derived(pullY >= PTR_TRIGGER);
</script>

<svelte:head>
	<title>잼얘좀</title>
	<meta name="description" content="재밌는 얘기 좀 해봐" />
</svelte:head>

{#if pullY > 0 || refreshing}
	<div
		class="pointer-events-none fixed left-1/2 z-50 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-base-300 bg-base-300 shadow-md"
		style="top: {Math.max(8, pullY - 28)}px; opacity: {refreshing
			? 1
			: Math.min(1, pullY / PTR_TRIGGER)}"
	>
		<RefreshCw
			class="h-4 w-4 {ptrReady || refreshing ? 'text-primary' : 'text-base-content/50'} {refreshing
				? 'animate-spin'
				: ''}"
			style={refreshing ? '' : `transform: rotate(${(pullY / PTR_TRIGGER) * 180}deg)`}
		/>
	</div>
{/if}

<QueryClientProvider client={queryClient}>
	{@render children()}
</QueryClientProvider>
