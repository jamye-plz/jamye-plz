<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { getTopic } from '$lib/api/topic.api';
	import { renderMarkdown } from '$lib/markdown';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import MessageCircle from '@lucide/svelte/icons/message-circle';

	const groupId = $derived(page.params.id!);
	const topicId = $derived(page.params.tid!);

	const topicQuery = createQuery(() => ({
		queryKey: ['topic', topicId],
		queryFn: () => getTopic(groupId, topicId)
	}));
</script>

<div class="min-h-screen bg-base-100">
	<AppHeader>
		<button
			onclick={() => goto(`/groups/${groupId}`)}
			class="btn -ml-2 btn-square btn-ghost btn-sm"
			aria-label="뒤로 가기"
		>
			<ArrowLeft class="h-5 w-5" />
		</button>
		<div class="min-w-0 flex-1">
			{#if topicQuery.data}
				<h1 class="truncate text-base font-semibold text-base-content">{topicQuery.data.title}</h1>
			{:else}
				<div class="h-4 w-48 skeleton"></div>
			{/if}
		</div>
		{#if topicQuery.data}
			<a
				href="/groups/{groupId}/topics/{topicId}/chat"
				class="btn btn-square shrink-0 btn-ghost btn-sm"
				aria-label="주제 채팅"
			>
				<MessageCircle class="h-5 w-5" />
			</a>
		{/if}
	</AppHeader>

	<main class="mx-auto max-w-lg space-y-6 px-4 py-6">
		{#if topicQuery.isPending}
			<p class="py-8 text-center text-sm text-base-content/70">불러오는 중...</p>
		{:else if topicQuery.isError}
			<p class="py-8 text-center text-sm text-error">주제를 불러올 수 없습니다.</p>
		{:else if topicQuery.data}
			{@const topic = topicQuery.data}
			<article class="space-y-4">
				<header class="space-y-2">
					<h2 class="text-xl leading-snug font-bold text-base-content">{topic.title}</h2>
					<div class="flex items-center gap-2 text-xs text-base-content/50">
						<span>{topic.author_nickname}</span>
						<span>·</span>
						<span
							>{new Date(topic.created_at).toLocaleDateString('ko-KR', {
								year: 'numeric',
								month: 'long',
								day: 'numeric'
							})}</span
						>
					</div>
				</header>

				{#if topic.body}
					<div class="prose max-w-none [&_pre]:overflow-x-auto">
						{@html renderMarkdown(topic.body)}
					</div>
				{:else}
					<p class="text-sm text-base-content/50 italic">아직 내용이 없습니다.</p>
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
									class="max-h-80 w-full rounded-xl bg-base-200 object-cover"
									loading="lazy"
								/>
							{/if}
						{/each}
					</div>
				{/if}
			</article>

			<div class="border-t border-base-300 pt-4">
				<a href="/groups/{groupId}/topics/{topicId}/chat" class="btn btn-block btn-primary">
					채팅에 참여하기
				</a>
			</div>
		{/if}
	</main>
</div>
