<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
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
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- action_url is a server-provided absolute app deep link (runtime string)
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
	<AppHeader>
		<div class="flex w-full items-center gap-3">
			<button
				onclick={() => goto(resolve('/groups'))}
				class="btn -ml-2 btn-square btn-ghost btn-sm"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="h-5 w-5" />
			</button>
			<h1 class="text-base font-semibold text-base-content">알림</h1>
			{#if notifsQuery.data && notifsQuery.data.unread_count > 0}
				<span class="badge badge-sm badge-primary">
					{notifsQuery.data.unread_count}
				</span>
			{/if}
		</div>
	</AppHeader>

	<main class="mx-auto max-w-lg px-4 py-4">
		{#if notifsQuery.isPending}
			<p class="py-8 text-center text-sm text-base-content/70">불러오는 중...</p>
		{:else if notifsQuery.isError}
			<p class="py-8 text-center text-sm text-error">알림을 불러올 수 없습니다.</p>
		{:else if notifsQuery.data && notifsQuery.data.items.length === 0}
			<p class="py-16 text-center text-sm text-base-content/50">아직 알림이 없어요</p>
		{:else if notifsQuery.data}
			<ul class="list gap-1" role="list" aria-label="알림 목록">
				{#each notifsQuery.data.items as n (n.id)}
					<li class="list-row p-0">
						<button
							onclick={() => open(n)}
							class="w-full rounded-xl border px-3 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-primary
								{n.read
								? 'border-base-300 bg-base-200 hover:bg-base-300'
								: 'border-primary/30 bg-primary/5 hover:bg-primary/10'}"
						>
							<div class="flex items-start gap-2.5">
								<span
									class="mt-1.5 status shrink-0 {n.read ? 'bg-transparent' : 'status-primary'}"
									aria-hidden="true"
								></span>
								<div class="min-w-0 flex-1 space-y-0.5">
									<p class="text-sm leading-snug font-medium text-base-content">{n.title}</p>
									{#if n.body}
										<p class="truncate text-sm text-base-content/70">{n.body}</p>
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
