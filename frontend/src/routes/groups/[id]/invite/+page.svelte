<script lang="ts">
	import { onMount } from 'svelte';
	import { createQuery, createMutation } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { createInvite, getMembers } from '$lib/api/group.api';
	import { ApiError } from '$lib/api/client';
	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import UserAvatar from '$lib/components/UserAvatar.svelte';

	// Always defined for the [id] route; assert so dependent calls stay typed.
	const groupId = $derived(page.params.id!);

	const membersQuery = createQuery(() => ({
		queryKey: ['members', groupId],
		queryFn: () => getMembers(groupId),
		enabled: !!groupId
	}));

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

<div class="min-h-screen bg-base-100">
	<header
		class="navbar sticky top-0 z-10 border-b border-base-300 bg-base-100/80 pt-[env(safe-area-inset-top)] pr-[max(0.75rem,env(safe-area-inset-right))] pl-[max(0.75rem,env(safe-area-inset-left))] backdrop-blur"
	>
		<div class="flex w-full items-center gap-3">
			<button
				onclick={() => goto(`/groups/${groupId}`)}
				class="btn btn-square btn-ghost btn-sm"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="h-5 w-5" />
			</button>
			<h1 class="text-base font-semibold text-base-content">초대</h1>
		</div>
	</header>

	<main class="mx-auto max-w-lg space-y-4 px-4 py-6">
		<p class="text-sm text-base-content/70">
			초대 링크를 만들어 공유하면, 받은 사람이 링크를 열어 바로 그룹에 참여할 수 있어요.
		</p>

		<button
			onclick={() => invite.mutate()}
			disabled={invite.isPending}
			class="btn btn-block btn-primary"
		>
			{invite.isPending ? '만드는 중...' : '초대 링크 만들기'}
		</button>

		{#if invite.isError}
			<p class="text-sm text-error" role="alert">{errorText(invite.error)}</p>
		{/if}

		{#if invite.data}
			<div class="card bg-base-200 card-border">
				<div class="card-body gap-3">
					<span class="text-xs text-base-content/50">초대 링크</span>
					<div class="flex items-center gap-2">
						<code class="flex-1 font-mono text-sm break-all text-base-content"
							>{inviteLink(invite.data.code)}</code
						>
						<button
							onclick={() => copyLink(invite.data!.code)}
							aria-label={copied ? '복사됨' : '링크 복사'}
							class="btn btn-square shrink-0 btn-ghost btn-sm"
						>
							<span class="swap swap-rotate {copied ? 'swap-active' : ''}">
								<Check class="swap-on h-4 w-4 text-primary" />
								<Copy class="swap-off h-4 w-4" />
							</span>
						</button>
					</div>
					{#if canShare}
						<button onclick={() => shareLink(invite.data!.code)} class="btn btn-block btn-primary">
							공유하기
						</button>
					{/if}
				</div>
			</div>
		{/if}

		<section class="space-y-2 pt-2">
			<h2 class="px-1 text-xs text-base-content/50">
				참여 멤버{#if membersQuery.data}
					({membersQuery.data.length})
				{/if}
			</h2>
			{#if membersQuery.isPending}
				<p class="px-1 text-sm text-base-content/50">불러오는 중...</p>
			{:else if membersQuery.isError}
				<p class="px-1 text-sm text-error" role="alert">멤버를 불러오지 못했어요.</p>
			{:else if membersQuery.data}
				<ul class="list rounded-xl border border-base-300 bg-base-200">
					{#each membersQuery.data as m (m.user_id)}
						<li class="list-row flex items-center gap-3">
							<UserAvatar url={m.avatar_url} name={m.nickname} class="shrink-0" />
							<span class="flex-1 truncate text-sm text-base-content">{m.nickname}</span>
							{#if m.role === 'owner'}
								<span class="badge shrink-0 badge-soft badge-sm badge-primary">그룹장</span>
							{:else}
								<span class="shrink-0 text-[11px] text-base-content/50">그룹원</span>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	</main>
</div>
