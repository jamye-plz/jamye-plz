<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { getTopic } from '$lib/api/topic.api';
	import { renderMarkdown } from '$lib/markdown';

	const groupId = $derived(page.params.id!);
	const topicId = $derived(page.params.tid!);

	const topicQuery = createQuery(() => ({
		queryKey: ['topic', topicId],
		queryFn: () => getTopic(groupId, topicId)
	}));
</script>

<div class="min-h-screen bg-base-100">
	<header class="sticky top-0 z-10 bg-base-100/80 backdrop-blur border-b border-base-300 px-4 py-3 flex items-center gap-3">
		<button
			onclick={() => goto(`/groups/${groupId}`)}
			class="btn btn-ghost btn-square btn-sm -ml-2"
			aria-label="뒤로 가기"
		>
			←
		</button>
		<div class="flex-1 min-w-0">
			{#if topicQuery.data}
				<h1 class="text-base font-semibold text-base-content truncate">{topicQuery.data.title}</h1>
			{:else}
				<div class="skeleton h-4 w-48"></div>
			{/if}
		</div>
		{#if topicQuery.data}
			<a
				href="/groups/{groupId}/topics/{topicId}/chat"
				class="btn btn-ghost btn-square btn-sm shrink-0"
				aria-label="주제 채팅"
			>
				💬
			</a>
		{/if}
	</header>

	<main class="px-4 py-6 space-y-6 max-w-lg mx-auto">
		{#if topicQuery.isPending}
			<p class="text-base-content/70 text-sm text-center py-8">불러오는 중...</p>
		{:else if topicQuery.isError}
			<p class="text-error text-sm text-center py-8">주제를 불러올 수 없습니다.</p>
		{:else if topicQuery.data}
			{@const topic = topicQuery.data}
			<article class="space-y-4">
				<header class="space-y-2">
					<h2 class="text-xl font-bold text-base-content leading-snug">{topic.title}</h2>
					<div class="flex items-center gap-2 text-xs text-base-content/50">
						<span>{topic.author_nickname}</span>
						<span>·</span>
						<span>{new Date(topic.created_at).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
					</div>
				</header>

				{#if topic.body}
					<div class="prose max-w-none [&_pre]:overflow-x-auto">
						{@html renderMarkdown(topic.body)}
					</div>
				{:else}
					<p class="text-base-content/50 text-sm italic">아직 내용이 없습니다.</p>
				{/if}

				{#if topic.tags.length > 0}
					<div class="flex flex-wrap gap-2" aria-label="태그">
						{#each topic.tags as tag}
							<span class="badge badge-ghost badge-sm">
								#{tag.tag}
							</span>
						{/each}
					</div>
				{/if}

				{#if topic.media.length > 0}
					<div class="space-y-2">
						{#each topic.media as media}
							{#if media.content_type.startsWith('image/')}
								<img
									src={media.url}
									alt="첨부 이미지"
									width={media.width ?? undefined}
									height={media.height ?? undefined}
									class="rounded-xl w-full object-cover max-h-80 bg-base-200"
									loading="lazy"
								/>
							{/if}
						{/each}
					</div>
				{/if}
			</article>

			<div class="border-t border-base-300 pt-4">
				<a
					href="/groups/{groupId}/topics/{topicId}/chat"
					class="btn btn-primary btn-block"
				>
					채팅에 참여하기
				</a>
			</div>
		{/if}
	</main>
</div>
