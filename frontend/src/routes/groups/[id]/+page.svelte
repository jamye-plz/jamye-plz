<script lang="ts">
	import {
		createQuery,
		createMutation,
		createInfiniteQuery,
		useQueryClient
	} from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { getGroup } from '$lib/api/group.api';
	import { listTopics, seedTopic, getTopicDates } from '$lib/api/topic.api';
	import DateDial from '$lib/components/DateDial.svelte';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import MessageCircle from '@lucide/svelte/icons/message-circle';
	import UserPlus from '@lucide/svelte/icons/user-plus';

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
		goto(url, { replaceState: true, keepFocus: true, noScroll: true });
	}

	const topicsQuery = createInfiniteQuery(() => ({
		queryKey: ['topics', groupId, selectedDate],
		queryFn: ({ pageParam }) =>
			listTopics(groupId, pageParam as string | undefined, selectedDate),
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
			<div class="flex-1 min-w-0">
				{#if groupQuery.data}
					<h1 class="text-base font-semibold text-base-content truncate">{groupQuery.data.name}</h1>
					<p class="text-xs text-base-content/50">{groupQuery.data.member_count}명</p>
				{:else}
					<div class="skeleton h-4 w-32"></div>
				{/if}
			</div>
			<div class="flex items-center gap-1">
				<a href="/groups/{groupId}/chat" class="btn btn-ghost btn-square btn-sm" aria-label="그룹 채팅">
					<MessageCircle class="w-5 h-5" />
				</a>
				<a href="/groups/{groupId}/invite" class="btn btn-ghost btn-square btn-sm" aria-label="초대">
					<UserPlus class="w-5 h-5" />
				</a>
			</div>
		</div>
	</header>

	<main>
		<div class="px-4 py-4 space-y-4 max-w-lg mx-auto">
			<form onsubmit={submitTopic} class="join w-full">
				<input
					bind:value={newTitle}
					type="text"
					placeholder="새 주제 던지기..."
					maxlength="256"
					aria-label="새 주제 제목"
					class="input join-item flex-1"
				/>
				<button
					type="submit"
					disabled={!newTitle.trim() || createTopic.isPending}
					class="btn btn-primary join-item shrink-0"
				>
					{createTopic.isPending ? '...' : '던지기'}
				</button>
			</form>

			{#if createTopic.isError}
				<p class="text-error text-xs px-1">주제를 만들지 못했어요. 다시 시도해 주세요.</p>
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
					<div class="skeleton h-9 w-40 rounded-xl"></div>
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
					<p class="text-base-content/70 text-sm text-center py-8">불러오는 중...</p>
				{:else if topicsQuery.isError}
					<p class="text-error text-sm text-center py-8">주제 목록을 불러올 수 없습니다.</p>
				{:else if allTopics.length === 0 && selectedDate}
					<div class="text-center py-16">
						<p class="text-base-content/50">이 날짜엔 주제가 없어요</p>
					</div>
				{:else if allTopics.length > 0}
					<ul class="space-y-3" role="list" aria-label="주제 목록">
						{#each allTopics as topic (topic.id)}
							<li>
								<a
									href="/groups/{groupId}/topics/{topic.id}/chat?date={selectedDate}"
									class="card card-border card-sm bg-base-200 hover:bg-base-300 transition-colors focus-visible:outline-2 focus-visible:outline-primary"
									aria-label={topic.title}
								>
									<div class="card-body">
										<div class="flex items-start justify-between gap-2">
											<span class="font-medium text-base-content leading-snug">{topic.title}</span>
											{#if topic.unread}
												<span class="shrink-0 status status-primary mt-1" aria-label="안 읽음"></span>
											{/if}
										</div>
										<div class="flex items-center gap-2 text-xs text-base-content/50">
											<span>{topic.author_nickname}</span>
											<span>·</span>
											<span>{timeLabel(topic.created_at)}</span>
										</div>
									</div>
								</a>
							</li>
						{/each}
					</ul>

					<div bind:this={sentinel} class="h-1"></div>
					{#if topicsQuery.isFetchingNextPage}
						<p class="text-base-content/50 text-xs text-center py-3">더 불러오는 중...</p>
					{/if}
				{/if}
			</div>
		</div>
	</main>
</div>
