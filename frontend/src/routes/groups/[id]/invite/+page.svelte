<script lang="ts">
	import { onMount } from 'svelte';
	import { createQuery, createMutation } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { createInvite, getMembers } from '$lib/api/group.api';
	import { ApiError } from '$lib/api/client';

	// Always defined for the [id] route; assert so dependent calls stay typed.
	const groupId = $derived(page.params.id!);

	const membersQuery = createQuery(() => ({
		queryKey: ['members', groupId],
		queryFn: () => getMembers(groupId),
		enabled: !!groupId
	}));

	function initial(name: string): string {
		return name?.trim()?.[0]?.toUpperCase() ?? '?';
	}

	let copied = $state(false);
	let canShare = $state(false);

	onMount(() => {
		canShare = browser && typeof navigator !== 'undefined' && typeof navigator.share === 'function';
	});

	const invite = createMutation(() => ({
		mutationFn: () => createInvite(groupId)
	}));

	function inviteLink(code: string): string {
		return browser ? `${location.origin}/invite/${code}` : `/invite/${code}`;
	}

	async function copyLink(code: string) {
		try {
			await navigator.clipboard.writeText(inviteLink(code));
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			// clipboard unavailable — user can still select the link manually
		}
	}

	async function shareLink(code: string) {
		try {
			await navigator.share({
				title: '잼얘좀 초대',
				text: '잼얘좀 그룹에 초대합니다. 링크를 열어 참여하세요.',
				url: inviteLink(code)
			});
		} catch {
			// user cancelled or share failed — no-op
		}
	}

	function errorText(err: unknown): string {
		if (err instanceof ApiError && err.status === 403) {
			return '그룹 소유자만 초대 코드를 만들 수 있어요.';
		}
		return '초대 코드를 만들지 못했어요. 다시 시도해 주세요.';
	}
</script>

<div class="min-h-screen bg-background">
	<header
		class="sticky top-0 z-10 bg-background/80 backdrop-blur border-b border-border px-4 py-3 flex items-center gap-3"
	>
		<button
			onclick={() => goto(`/groups/${groupId}`)}
			class="p-2 -ml-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors"
			aria-label="뒤로 가기"
		>
			←
		</button>
		<h1 class="text-base font-semibold text-text-primary">초대</h1>
	</header>

	<main class="px-4 py-6 space-y-4 max-w-lg mx-auto">
		<p class="text-text-secondary text-sm">
			초대 링크를 만들어 공유하면, 받은 사람이 링크를 열어 바로 그룹에 참여할 수 있어요.
		</p>

		<button
			onclick={() => invite.mutate()}
			disabled={invite.isPending}
			class="w-full py-3 rounded-xl bg-accent text-white font-medium text-sm disabled:opacity-40 transition-opacity hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
		>
			{invite.isPending ? '만드는 중...' : '초대 링크 만들기'}
		</button>

		{#if invite.isError}
			<p class="text-danger text-sm" role="alert">{errorText(invite.error)}</p>
		{/if}

		{#if invite.data}
			<div class="space-y-3 rounded-xl bg-surface border border-border p-4">
				<span class="text-xs text-text-muted">초대 링크</span>
				<div class="flex items-center gap-2">
					<code class="flex-1 font-mono text-sm text-text-primary break-all">{inviteLink(invite.data.code)}</code>
					<button
						onclick={() => copyLink(invite.data!.code)}
						class="shrink-0 px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-text-secondary text-sm hover:text-text-primary transition-colors focus-visible:outline-2 focus-visible:outline-accent"
					>
						{copied ? '복사됨' : '복사'}
					</button>
				</div>
				{#if canShare}
					<button
						onclick={() => shareLink(invite.data!.code)}
						class="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-medium transition-opacity hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
					>
						공유하기
					</button>
				{/if}
			</div>
		{/if}

		<section class="space-y-2 pt-2">
			<h2 class="text-xs text-text-muted px-1">
				참여 멤버{#if membersQuery.data}
					({membersQuery.data.length})
				{/if}
			</h2>
			{#if membersQuery.isPending}
				<p class="text-sm text-text-muted px-1">불러오는 중...</p>
			{:else if membersQuery.isError}
				<p class="text-sm text-danger px-1" role="alert">멤버를 불러오지 못했어요.</p>
			{:else if membersQuery.data}
				<ul class="rounded-xl bg-surface border border-border divide-y divide-border">
					{#each membersQuery.data as m (m.user_id)}
						<li class="flex items-center gap-3 p-3">
							{#if m.avatar_url}
								<img
									src={m.avatar_url}
									alt={m.nickname}
									class="w-9 h-9 rounded-full object-cover bg-surface-elevated shrink-0"
								/>
							{:else}
								<div
									class="w-9 h-9 rounded-full bg-accent/20 text-accent flex items-center justify-center text-sm font-semibold shrink-0"
									aria-hidden="true"
								>
									{initial(m.nickname)}
								</div>
							{/if}
							<span class="flex-1 text-sm text-text-primary truncate">{m.nickname}</span>
							{#if m.role === 'owner'}
								<span
									class="shrink-0 text-[11px] font-medium text-accent bg-accent/10 px-2 py-0.5 rounded-full"
									>그룹장</span
								>
							{:else}
								<span class="shrink-0 text-[11px] text-text-muted">그룹원</span>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	</main>
</div>
