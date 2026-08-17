<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import {
		createQuery,
		createMutation,
		createInfiniteQuery,
		useQueryClient
	} from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { getGroup } from '$lib/api/group.api';
	import { listTopics, seedTopic, getTopicDates } from '$lib/api/topic.api';
	import DateDial from '$lib/components/DateDial.svelte';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import MessageCircle from '@lucide/svelte/icons/message-circle';
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Settings from '@lucide/svelte/icons/settings';
	import { fade } from 'svelte/transition';
	import { prefersReducedMotion } from 'svelte/motion';

	const groupId = $derived(page.params.id ?? '');
	const queryClient = useQueryClient();

	const groupQuery = createQuery(() => ({
		queryKey: ['group', groupId],
		queryFn: () => getGroup(groupId),
		enabled: !!groupId
	}));

	const datesQuery = createQuery(() => ({
		queryKey: ['topic-dates', groupId],
		queryFn: () => getTopicDates(groupId),
		enabled: !!groupId
	}));

	// Authoritative "today" string from the server (Asia/Seoul YYYY-MM-DD).
	const serverToday = $derived(datesQuery.data?.today ?? '');

	// Selected date is driven by the URL (?date=YYYY-MM-DD) so it survives
	// back-navigation from a topic chatroom. Only the first entry (no param)
	// defaults to today — every later remount restores the chosen date.
	const urlDate = $derived(page.url.searchParams.get('date'));
	const selectedDate = $derived(urlDate ?? serverToday);

	function selectDate(date: string) {
		const url = new URL(page.url);
		url.searchParams.set('date', date);
		// replaceState: a date tap shouldn't stack history entries, but the updated
		// URL is exactly what we return to when coming back from a topic chatroom.
		// url is derived from page.url (already resolved, same-origin); resolve()'s
		// typed-routes signature can't accept a runtime URL/string, so navigate directly.
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- url derived from page.url, already resolved
		goto(url, { replaceState: true, keepFocus: true, noScroll: true });
	}

	const topicsQuery = createInfiniteQuery(() => ({
		queryKey: ['topics', groupId, selectedDate],
		queryFn: ({ pageParam }) => listTopics(groupId, pageParam as string | undefined, selectedDate),
		initialPageParam: undefined as string | undefined,
		getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
		enabled: !!selectedDate && !!groupId
	}));

	const allTopics = $derived(topicsQuery.data?.pages.flatMap((p) => p.items) ?? []);

	let newTitle = $state('');
	const createTopic = createMutation(() => ({
		mutationFn: (title: string) => seedTopic(groupId, title),
		onSuccess: () => {
			newTitle = '';
			// Invalidate both the date list and all topics for this group.
			queryClient.invalidateQueries({ queryKey: ['topic-dates', groupId] });
			queryClient.invalidateQueries({ queryKey: ['topics', groupId] });
			// A new topic is posted under today; jump to today so it's visible even
			// when the user was viewing an older date (otherwise it looks lost).
			if (serverToday && selectedDate !== serverToday) selectDate(serverToday);
		}
	}));

	function submitTopic(e: SubmitEvent) {
		e.preventDefault();
		const title = newTitle.trim();
		if (!title || createTopic.isPending) return;
		createTopic.mutate(title);
	}

	// Infinite scroll: load the next page when the sentinel scrolls into view.
	let sentinel = $state<HTMLElement | null>(null);
	$effect(() => {
		const el = sentinel;
		if (!el) return;
		const io = new IntersectionObserver(
			(entries) => {
				if (
					entries[0].isIntersecting &&
					topicsQuery.hasNextPage &&
					!topicsQuery.isFetchingNextPage
				) {
					topicsQuery.fetchNextPage();
				}
			},
			{ rootMargin: '200px' }
		);
		io.observe(el);
		return () => io.disconnect();
	});

	function timeLabel(iso: string): string {
		return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
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
			<div class="min-w-0 flex-1">
				<h1
					data-route-focus-target
					tabindex="-1"
					aria-label={groupQuery.data?.name ?? '그룹'}
					class="truncate text-base font-semibold text-base-content"
				>
					{#if groupQuery.data}
						{groupQuery.data.name}
					{:else}
						<span aria-hidden="true" class="block h-4 w-32 skeleton"></span>
					{/if}
				</h1>
				{#if groupQuery.data}
					<p class="text-xs text-[var(--color-text-muted)]">{groupQuery.data.member_count}명</p>
				{/if}
			</div>
			<div class="flex items-center gap-1">
				<a
					href={resolve(`/groups/${groupId}/chat`)}
					class="btn btn-square btn-ghost"
					aria-label="그룹 채팅"
				>
					<MessageCircle class="h-5 w-5" />
				</a>
				<a
					href={resolve(`/groups/${groupId}/invite`)}
					class="btn btn-square btn-ghost"
					aria-label="초대"
				>
					<UserPlus class="h-5 w-5" />
				</a>
				<a
					href={resolve(`/groups/${groupId}/settings`)}
					class="btn btn-square btn-ghost"
					aria-label="그룹 설정"
				>
					<Settings class="h-5 w-5" />
				</a>
			</div>
		</div>
	</AppHeader>

	<main id="main-content">
		<div class="mx-auto max-w-[720px] space-y-4 px-4 py-4 md:px-6">
			<div class="elevation-1 rounded-xl bg-[var(--color-surface-raised)] p-4 md:p-5">
				<form onsubmit={submitTopic} class="flex w-full items-stretch gap-2">
					<input
						id="new-topic-input"
						bind:value={newTitle}
						type="text"
						placeholder="새 주제 던지기..."
						maxlength="256"
						aria-label="새 주제 제목"
						class="input min-w-0 flex-1 rounded-lg"
					/>
					<button
						type="submit"
						disabled={!newTitle.trim() || createTopic.isPending}
						class="btn shrink-0 rounded-lg px-5 btn-primary"
					>
						{createTopic.isPending ? '...' : '던지기'}
					</button>
				</form>
			</div>

			{#if createTopic.isError}
				<p class="px-1 text-xs text-error">주제를 만들지 못했어요. 다시 시도해 주세요.</p>
			{/if}

			<!-- Date dial: directly below the composer, same width. Drag/scroll to a
			     date under the center indicator; releasing snaps and selects it. -->
			{#if datesQuery.data && datesQuery.data.dates.length > 0}
				<DateDial
					dates={datesQuery.data.dates}
					selected={selectedDate}
					today={serverToday}
					onselect={selectDate}
				/>
			{:else if datesQuery.isPending}
				<div class="flex justify-center py-2" aria-hidden="true">
					<div class="h-9 w-40 skeleton rounded-lg"></div>
				</div>
			{/if}

			<div
				id="topics-panel"
				role="tabpanel"
				aria-label="선택된 날짜의 주제"
				tabindex="0"
				class="space-y-3 outline-none"
			>
				{#if topicsQuery.isPending && selectedDate}
					<div class="space-y-3" aria-label="주제 목록을 불러오는 중" aria-busy="true">
						{#each [1, 2, 3] as card (card)}
							<div
								class="elevation-1 space-y-3 rounded-xl border border-base-300 bg-[var(--color-surface-raised)] p-4 md:p-5"
							>
								<span class="block h-5 w-2/3 skeleton"></span>
								<span class="block h-3 w-2/5 skeleton"></span>
							</div>
						{/each}
					</div>
				{:else if topicsQuery.isError}
					<p class="py-8 text-center text-sm text-error">주제 목록을 불러올 수 없습니다.</p>
				{:else if allTopics.length === 0 && selectedDate}
					<div
						class="py-16 text-center"
						in:fade={{ duration: prefersReducedMotion.current ? 0 : 300 }}
					>
						<p class="text-[var(--color-text-muted)]">이 날짜엔 주제가 없어요</p>
					</div>
				{:else if allTopics.length > 0}
					<ul class="space-y-3" role="list" aria-label="주제 목록">
						{#each allTopics as topic (topic.id)}
							<li>
								<a
									href={resolve(`/groups/${groupId}/topics/${topic.id}/chat?date=${selectedDate}`)}
									class="elevation-1 card rounded-xl border border-base-300 bg-[var(--color-surface-raised)] transition-colors hover:border-primary/40 focus-visible:outline-3 focus-visible:outline-primary {topic.unread
										? 'ring-2 ring-primary'
										: ''}"
									aria-label={topic.unread ? `${topic.title}, 안 읽음` : topic.title}
								>
									<div class="card-body gap-2 p-4 md:p-5">
										<div class="flex items-start justify-between gap-3">
											<span class="text-[18px] leading-[1.45] font-[650] text-base-content"
												>{topic.title}</span
											>
											{#if topic.unread}
												<span class="badge shrink-0 badge-soft badge-sm badge-primary">안 읽음</span
												>
											{/if}
										</div>
										<div
											class="flex items-center gap-2 text-[13px] text-[var(--color-text-muted)] tabular-nums"
										>
											<span>{topic.author_nickname}</span>
											<span aria-hidden="true">·</span>
											<span>{timeLabel(topic.created_at)}</span>
										</div>
									</div>
								</a>
							</li>
						{/each}
					</ul>

					<div bind:this={sentinel} class="h-1"></div>
					{#if topicsQuery.isFetchingNextPage}
						<p class="py-3 text-center text-xs text-[var(--color-text-muted)]">더 불러오는 중...</p>
					{/if}
				{/if}
			</div>
		</div>
	</main>
</div>
