<script lang="ts">
	import '../app.css';
	import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
	import { onDestroy, onMount } from 'svelte';

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
</script>

<svelte:head>
	<title>잼얘좀</title>
	<meta name="description" content="재밌는 얘기 좀 해봐" />
</svelte:head>

<QueryClientProvider client={queryClient}>
	{@render children()}
</QueryClientProvider>
