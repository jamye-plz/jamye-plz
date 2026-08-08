<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { listNotifications, markNotificationRead } from '$lib/api/notification.api';
	import type { AppNotification } from '$lib/types/notification.types';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import { fade } from 'svelte/transition';
	import { prefersReducedMotion } from 'svelte/motion';

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

<div class="min-h-dvh bg-base-100">
	<AppHeader>
		<div class="flex w-full items-center gap-3">
			<button
				onclick={() => goto(resolve('/groups'))}
				class="btn -ml-2 btn-square btn-ghost"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="h-5 w-5" />
			</button>
			<h1 class="text-base font-semibold text-base-content">알림</h1>
			{#if notifsQuery.data && notifsQuery.data.unread_count > 0}
				<span class="badge badge-sm badge-primary">
					{notifsQuery.data.unread_count}
					<span class="sr-only">개 읽지 않은 알림</span>
				</span>
			{/if}
		</div>
	</AppHeader>

	<main id="main-content" class="mx-auto max-w-[720px] px-4 py-4 md:px-6">
		{#if notifsQuery.isPending}
			<ul class="list" aria-label="알림 목록을 불러오는 중" aria-busy="true">
				{#each [1, 2, 3] as row (row)}
					<li class="list-row min-h-16 border-b border-base-300 p-0 last:border-b-0">
						<div class="min-h-16 w-full space-y-2 px-4 py-3">
							<span class="block h-4 w-48 max-w-[75%] skeleton"></span>
							<span class="block h-3 w-32 max-w-[55%] skeleton"></span>
						</div>
					</li>
				{/each}
			</ul>
		{:else if notifsQuery.isError}
			<p class="py-8 text-center text-sm text-error">알림을 불러올 수 없습니다.</p>
		{:else if notifsQuery.data && notifsQuery.data.items.length === 0}
			<p
				class="py-16 text-center text-sm text-[var(--color-text-muted)]"
				in:fade={{ duration: prefersReducedMotion.current ? 0 : 300 }}
			>
				아직 알림이 없어요
			</p>
		{:else if notifsQuery.data}
			<ul class="list" role="list" aria-label="알림 목록">
				{#each notifsQuery.data.items as n (n.id)}
					<li class="list-row min-h-16 border-b border-base-300 p-0 last:border-b-0">
						<button
							onclick={() => open(n)}
							class="min-h-16 w-full border-l-2 px-4 py-3 text-left transition-colors focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-primary
								{n.read
								? 'border-transparent hover:bg-[var(--color-surface-raised)]'
								: 'border-primary bg-[var(--color-surface-blush)] hover:bg-base-200'}"
						>
							<div class="flex items-start gap-3">
								<span
									class="mt-1.5 status shrink-0 {n.read ? 'bg-transparent' : 'status-primary'}"
									aria-hidden="true"
								></span>
								<div class="min-w-0 flex-1 space-y-0.5">
									<div class="flex items-start justify-between gap-3">
										<p class="text-sm leading-snug font-medium text-base-content">{n.title}</p>
										{#if !n.read}
											<span class="badge shrink-0 badge-soft badge-sm badge-primary">안 읽음</span>
										{/if}
									</div>
									{#if n.body}
										<p class="truncate text-sm text-[var(--color-text-muted)]">{n.body}</p>
									{/if}
									<p class="text-[13px] text-[var(--color-text-muted)] tabular-nums">
										{timeAgo(n.created_at)}
									</p>
								</div>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</main>
</div>
