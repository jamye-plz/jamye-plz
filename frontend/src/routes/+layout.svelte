<script lang="ts">
	import '../app.css';
	import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
	import { onDestroy } from 'svelte';

	let { children } = $props();

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
	<meta name="description" content="폐쇄 그룹에서 주제를 던지고 실시간으로 떠드는 공간" />
</svelte:head>

<QueryClientProvider client={queryClient}>
	{@render children()}
</QueryClientProvider>
