<script lang="ts">
	import { tick } from 'svelte';
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

	// Compute yesterday purely from the server's today string — no browser Date.now().
	function subtractOneDay(yyyymmdd: string): string {
		const [y, m, d] = yyyymmdd.split('-').map(Number);
		const dt = new Date(Date.UTC(y!, m! - 1, d!));
		dt.setUTCDate(dt.getUTCDate() - 1);
		const yy = dt.getUTCFullYear();
		const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
		const dd = String(dt.getUTCDate()).padStart(2, '0');
		return `${yy}-${mm}-${dd}`;
	}

	function tabLabel(date: string, today: string): string {
		if (!today) return date;
		if (date === today) return '오늘';
		if (date === subtractOneDay(today)) return '어제';
		return date;
	}

	// Selected date — empty until datesQuery loads, then set to today once.
	let selectedDate = $state('');

	$effect(() => {
		if (selectedDate === '' && datesQuery.data?.today) {
			selectedDate = datesQuery.data.today;
		}
	});

	// Horizontally-scrollable date strip: whenever the selection changes (incl. the
	// initial default of today), recenter the selected tab within the strip.
	let tablistEl = $state<HTMLElement | null>(null);
	function centerSelectedTab() {
		const el = tablistEl?.querySelector<HTMLElement>(`[data-date="${selectedDate}"]`);
		if (!el) return;
		const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		el.scrollIntoView({ inline: 'center', block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
	}
	$effect(() => {
		selectedDate; // re-run when the selected date changes
		datesQuery.data; // and once the tabs have rendered
		if (!selectedDate) return;
		tick().then(centerSelectedTab);
	});

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

<div class="min-h-screen bg-background">
	<header
		class="sticky top-0 z-10 bg-background/80 backdrop-blur border-b border-border px-4 py-3 flex items-center gap-3"
	>
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

	<main>
		<div class="px-4 py-4 space-y-4 max-w-lg mx-auto">
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

			<!-- Date strip: directly below the composer, same width, horizontally scrollable.
			     Selecting a date recenters it (see centerSelectedTab). -->
			{#if datesQuery.data && datesQuery.data.dates.length > 0}
				<div
					bind:this={tablistEl}
					role="tablist"
					aria-label="날짜 선택"
					class="flex gap-2 overflow-x-auto -mx-1 px-1 py-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
				>
					{#each datesQuery.data.dates as date (date)}
						<button
							type="button"
							role="tab"
							data-date={date}
							aria-selected={date === selectedDate}
							aria-controls="topics-panel"
							onclick={() => (selectedDate = date)}
							class="shrink-0 min-h-[40px] px-4 py-2 rounded-full text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent whitespace-nowrap
								{date === selectedDate
								? 'bg-accent text-white'
								: 'bg-surface text-text-secondary hover:bg-surface-elevated hover:text-text-primary'}"
						>
							{tabLabel(date, serverToday)}
						</button>
					{/each}
				</div>
			{:else if datesQuery.isPending}
				<div class="flex gap-2 overflow-x-auto py-1" aria-hidden="true">
					{#each [1, 2, 3] as i (i)}
						<div class="shrink-0 h-[40px] w-16 bg-surface-elevated rounded-full animate-pulse"></div>
					{/each}
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
					<p class="text-text-secondary text-sm text-center py-8">불러오는 중...</p>
				{:else if topicsQuery.isError}
					<p class="text-danger text-sm text-center py-8">주제 목록을 불러올 수 없습니다.</p>
				{:else if allTopics.length === 0 && selectedDate}
					<div class="text-center py-16">
						<p class="text-text-muted">이 날짜엔 주제가 없어요</p>
					</div>
				{:else if allTopics.length > 0}
					<ul class="space-y-3" role="list" aria-label="주제 목록">
						{#each allTopics as topic (topic.id)}
							<li>
								<a
									href="/groups/{groupId}/topics/{topic.id}/chat"
									class="block px-4 py-4 rounded-xl bg-surface hover:bg-surface-elevated border border-border transition-colors focus-visible:outline-2 focus-visible:outline-accent"
									aria-label={topic.title}
								>
									<div class="space-y-2">
										<div class="flex items-start justify-between gap-2">
											<span class="font-medium text-text-primary leading-snug">{topic.title}</span>
											{#if topic.unread}
												<span
													class="shrink-0 w-2.5 h-2.5 rounded-full bg-blue-500 mt-1"
													aria-label="안 읽음"
												></span>
											{/if}
										</div>
										<div class="flex items-center gap-2 text-xs text-text-muted">
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
						<p class="text-text-muted text-xs text-center py-3">더 불러오는 중...</p>
					{/if}
				{/if}
			</div>
		</div>
	</main>
</div>
