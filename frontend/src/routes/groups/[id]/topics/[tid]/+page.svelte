<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
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

<div class="min-h-dvh bg-base-100">
	<AppHeader>
		<button
			onclick={() => goto(resolve(`/groups/${groupId}`))}
			class="btn -ml-2 btn-square btn-ghost"
			aria-label="뒤로 가기"
		>
			<ArrowLeft class="h-5 w-5" />
		</button>
		<div class="min-w-0 flex-1">
			<h1
				data-route-focus-target
				tabindex="-1"
				aria-label={topicQuery.data?.title ?? '주제'}
				class="truncate text-base font-semibold text-base-content"
			>
				{#if topicQuery.data}
					{topicQuery.data.title}
				{:else}
					<span aria-hidden="true" class="block h-4 w-48 skeleton"></span>
				{/if}
			</h1>
		</div>
		{#if topicQuery.data}
			<a
				href={resolve(`/groups/${groupId}/topics/${topicId}/chat`)}
				class="btn btn-square shrink-0 btn-ghost"
				aria-label="주제 채팅"
			>
				<MessageCircle class="h-5 w-5" />
			</a>
		{/if}
	</AppHeader>

	<main id="main-content" class="mx-auto max-w-(--container-conversation) px-4 py-6 md:px-6">
		{#if topicQuery.isPending}
			<p class="py-8 text-center text-sm text-(--color-text-muted)">불러오는 중...</p>
		{:else if topicQuery.isError}
			<p class="py-8 text-center text-sm text-error">주제를 불러올 수 없습니다.</p>
		{:else if topicQuery.data}
			{@const topic = topicQuery.data}
			<div class="space-y-4">
				<article
					class="elevation-1 space-y-4 rounded-xl border border-base-300 bg-(--color-surface-raised) p-4 md:p-5"
				>
					<header class="space-y-2">
						<h2 class="text-[18px] leading-[1.45] font-[650] text-base-content">{topic.title}</h2>
						<div class="flex items-center gap-2 text-[13px] text-(--color-text-muted) tabular-nums">
							<span>{topic.author_nickname}</span>
							<span aria-hidden="true">·</span>
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
							<!-- eslint-disable-next-line svelte/no-at-html-tags -- output sanitized by renderMarkdown (DOMPurify) -->
							{@html renderMarkdown(topic.body)}
						</div>
					{:else}
						<p class="text-sm text-(--color-text-muted) italic">아직 내용이 없습니다.</p>
					{/if}

					{#if topic.tags.length > 0}
						<div class="flex flex-wrap gap-2" aria-label="태그">
							{#each topic.tags as tag (tag.tag)}
								<span class="badge badge-ghost badge-sm">
									#{tag.tag}
								</span>
							{/each}
						</div>
					{/if}

					{#if topic.media.length > 0}
						<div class="space-y-2">
							{#each topic.media as media (media.id)}
								{#if media.content_type.startsWith('image/')}
									<img
										src={media.url}
										alt="첨부 이미지"
										width={media.width ?? undefined}
										height={media.height ?? undefined}
										class="max-h-80 w-full rounded-sm bg-base-200 object-cover"
										style={media.width && media.height
											? `aspect-ratio: ${media.width} / ${media.height}`
											: 'min-height: 10rem'}
										loading="lazy"
									/>
								{/if}
							{/each}
						</div>
					{/if}
				</article>

				<div class="pt-2">
					<a
						href={resolve(`/groups/${groupId}/topics/${topicId}/chat`)}
						class="btn btn-block rounded-lg btn-primary"
					>
						채팅에 참여하기
					</a>
				</div>
			</div>
		{/if}
	</main>
</div>
