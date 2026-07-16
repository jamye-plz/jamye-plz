<script lang="ts">
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listNotifications, markNotificationRead } from '$lib/api/notification.api';
	import type { AppNotification } from '$lib/types/notification.types';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';

	const queryClient = useQueryClient();
	const notifsQuery = createQuery(() => ({
		queryKey: ['notifications'],
		queryFn: listNotifications
	}));

	const markRead = createMutation(() => ({
		mutationFn: (id: string) => markNotificationRead(id),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] })
	}));

	async function open(n: AppNotification) {
		if (!n.read) markRead.mutate(n.id);
		if (n.action_url) goto(n.action_url);
	}

	function timeAgo(iso: string): string {
		const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
		if (seconds < 60) return '방금';
		const m = Math.floor(seconds / 60);
		if (m < 60) return `${m}분 전`;
		const h = Math.floor(m / 60);
		if (h < 24) return `${h}시간 전`;
		const d = Math.floor(h / 24);
		if (d < 7) return `${d}일 전`;
		return new Date(iso).toLocaleDateString('ko-KR');
	}
</script>

<div class="min-h-screen bg-base-100">
	<header class="navbar sticky top-0 z-10 bg-base-100/80 backdrop-blur border-b border-base-300">
		<div class="w-full flex items-center gap-3">
			<button
				onclick={() => goto('/groups')}
				class="btn btn-ghost btn-square btn-sm -ml-2"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="w-5 h-5" />
			</button>
			<h1 class="text-base font-semibold text-base-content">알림</h1>
			{#if notifsQuery.data && notifsQuery.data.unread_count > 0}
				<span class="badge badge-primary badge-sm">
					{notifsQuery.data.unread_count}
				</span>
			{/if}
		</div>
	</header>

	<main class="px-4 py-4 max-w-lg mx-auto">
		{#if notifsQuery.isPending}
			<p class="text-base-content/70 text-sm text-center py-8">불러오는 중...</p>
		{:else if notifsQuery.isError}
			<p class="text-error text-sm text-center py-8">알림을 불러올 수 없습니다.</p>
		{:else if notifsQuery.data && notifsQuery.data.items.length === 0}
			<p class="text-base-content/50 text-sm text-center py-16">아직 알림이 없어요</p>
		{:else if notifsQuery.data}
			<ul class="list gap-1" role="list" aria-label="알림 목록">
				{#each notifsQuery.data.items as n (n.id)}
					<li class="list-row p-0">
						<button
							onclick={() => open(n)}
							class="w-full text-left px-3 py-3 rounded-xl border transition-colors focus-visible:outline-2 focus-visible:outline-primary
								{n.read
								? 'bg-base-200 border-base-300 hover:bg-base-300'
								: 'bg-primary/5 border-primary/30 hover:bg-primary/10'}"
						>
							<div class="flex items-start gap-2.5">
								<span
									class="mt-1.5 shrink-0 status {n.read ? 'bg-transparent' : 'status-primary'}"
									aria-hidden="true"
								></span>
								<div class="min-w-0 flex-1 space-y-0.5">
									<p class="text-sm font-medium text-base-content leading-snug">{n.title}</p>
									{#if n.body}
										<p class="text-sm text-base-content/70 truncate">{n.body}</p>
									{/if}
									<p class="text-xs text-base-content/50">{timeAgo(n.created_at)}</p>
								</div>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</main>
</div>
