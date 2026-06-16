<script lang="ts">
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { getGroup } from '$lib/api/group.api';
	import { listTopics, seedTopic } from '$lib/api/topic.api';

	// Svelte 5: page is a rune-based store
	const groupId = $derived(page.params.id);

	const queryClient = useQueryClient();

	const groupQuery = createQuery(() => ({
		queryKey: ['group', groupId],
		queryFn: () => getGroup(groupId)
	}));

	const topicsQuery = createQuery(() => ({
		queryKey: ['topics', groupId],
		queryFn: () => listTopics(groupId)
	}));

	let newTitle = $state('');

	const createTopic = createMutation(() => ({
		mutationFn: (title: string) => seedTopic(groupId, title),
		onSuccess: () => {
			newTitle = '';
			queryClient.invalidateQueries({ queryKey: ['topics', groupId] });
		}
	}));

	function submitTopic(e: SubmitEvent) {
		e.preventDefault();
		const title = newTitle.trim();
		if (!title || createTopic.isPending) return;
		createTopic.mutate(title);
	}
</script>

<div class="min-h-screen bg-background">
	<header class="sticky top-0 z-10 bg-background/80 backdrop-blur border-b border-border px-4 py-3 flex items-center gap-3">
		<button
			onclick={() => goto('/groups')}
			class="p-2 -ml-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors"
			aria-label="뒤로 가기"
		>
			←
		</button>
		<div class="flex-1 min-w-0">
			{#if groupQuery.data}
				<h1 class="text-base font-semibold text-text-primary truncate">{groupQuery.data.name}</h1>
				<p class="text-xs text-text-muted">{groupQuery.data.member_count}명</p>
			{:else}
				<div class="h-4 w-32 bg-surface-elevated rounded animate-pulse"></div>
			{/if}
		</div>
		<div class="flex items-center gap-1">
			<a
				href="/groups/{groupId}/chat"
				class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors"
				aria-label="그룹 채팅"
			>
				💬
			</a>
			<a
				href="/groups/{groupId}/invite"
				class="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors"
				aria-label="초대"
			>
				👋
			</a>
		</div>
	</header>

	<main class="px-4 py-6 space-y-4 max-w-lg mx-auto">
		<form onsubmit={submitTopic} class="flex items-center gap-2">
			<input
				bind:value={newTitle}
				type="text"
				placeholder="새 주제 던지기..."
				maxlength="256"
				aria-label="새 주제 제목"
				class="flex-1 px-3 py-2.5 rounded-xl bg-surface-elevated border border-border text-text-primary placeholder:text-text-muted text-sm focus-visible:outline-2 focus-visible:outline-accent"
			/>
			<button
				type="submit"
				disabled={!newTitle.trim() || createTopic.isPending}
				class="shrink-0 px-4 py-2.5 rounded-xl bg-accent text-white font-medium text-sm disabled:opacity-40 transition-opacity hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
			>
				{createTopic.isPending ? '...' : '던지기'}
			</button>
		</form>

		{#if createTopic.isError}
			<p class="text-danger text-xs px-1">주제를 만들지 못했어요. 다시 시도해 주세요.</p>
		{/if}

		{#if topicsQuery.isPending}
			<p class="text-text-secondary text-sm text-center py-8">불러오는 중...</p>
		{:else if topicsQuery.isError}
			<p class="text-danger text-sm text-center py-8">주제 목록을 불러올 수 없습니다.</p>
		{:else if topicsQuery.data && topicsQuery.data.items.length === 0}
			<div class="text-center py-16">
				<p class="text-text-muted">아직 주제가 없어요</p>
			</div>
		{:else if topicsQuery.data}
			<ul class="space-y-3" role="list" aria-label="주제 목록">
				{#each topicsQuery.data.items as topic (topic.id)}
					<li>
						<a
							href="/groups/{groupId}/topics/{topic.id}"
							class="block px-4 py-4 rounded-xl bg-surface hover:bg-surface-elevated border border-border transition-colors focus-visible:outline-2 focus-visible:outline-accent"
							aria-label={topic.title}
						>
							<div class="space-y-2">
								<div class="flex items-start justify-between gap-2">
									<span class="font-medium text-text-primary leading-snug">{topic.title}</span>
									{#if topic.status === 'enriched'}
										<span class="shrink-0 text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent">정리됨</span>
									{/if}
								</div>
								<div class="flex items-center gap-2 text-xs text-text-muted">
									<span>{topic.author_nickname}</span>
									<span>·</span>
									<span>{new Date(topic.created_at).toLocaleDateString('ko-KR')}</span>
								</div>
							</div>
						</a>
					</li>
				{/each}
			</ul>
		{/if}
	</main>
</div>
