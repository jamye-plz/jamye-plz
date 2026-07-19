<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { getGroup, renameGroup, deleteGroup, leaveGroup } from '$lib/api/group.api';
	import { getMe } from '$lib/api/auth.api';
	import { ApiError } from '$lib/api/client';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';

	// Always defined for the [id] route; assert so dependent calls stay typed.
	const groupId = $derived(page.params.id!);
	const queryClient = useQueryClient();

	const groupQuery = createQuery(() => ({
		queryKey: ['group', groupId],
		queryFn: () => getGroup(groupId),
		enabled: !!groupId
	}));
	const meQuery = createQuery(() => ({ queryKey: ['me'], queryFn: getMe }));

	const isOwner = $derived(
		!!groupQuery.data && !!meQuery.data && groupQuery.data.owner_id === meQuery.data.id
	);

	function renameErrorText(err: unknown): string {
		if (err instanceof ApiError) {
			if (err.status === 403) return '그룹장만 이름을 수정할 수 있어요.';
			if (err.status === 404) return '그룹을 찾을 수 없어요.';
		}
		return '이름을 저장하지 못했어요. 다시 시도해 주세요.';
	}

	function deleteErrorText(err: unknown): string {
		if (err instanceof ApiError) {
			if (err.status === 403) return '그룹장만 그룹을 삭제할 수 있어요.';
			if (err.status === 404) return '그룹을 찾을 수 없어요.';
		}
		return '그룹을 삭제하지 못했어요. 다시 시도해 주세요.';
	}

	function leaveErrorText(err: unknown): string {
		if (err instanceof ApiError) {
			if (err.status === 409) return '소유권을 먼저 다른 멤버에게 이양해야 나갈 수 있어요.';
			if (err.status === 404) return '그룹을 찾을 수 없어요.';
		}
		return '그룹을 나가지 못했어요. 다시 시도해 주세요.';
	}

	// --- Rename ---
	let groupName = $state('');
	let dirty = $state(false);
	let saved = $state(false);

	// Seed the input from the loaded group until the user starts editing.
	$effect(() => {
		if (groupQuery.data && !dirty) groupName = groupQuery.data.name;
	});

	const rename = createMutation(() => ({
		mutationFn: (name: string) => renameGroup(groupId, name),
		onSuccess: (group) => {
			queryClient.setQueryData(['group', groupId], group);
			queryClient.invalidateQueries({ queryKey: ['groups'] });
			dirty = false;
			saved = true;
			setTimeout(() => (saved = false), 1500);
		}
	}));

	function onSaveName(e: SubmitEvent) {
		e.preventDefault();
		if (!isOwner) return;
		const name = groupName.trim();
		if (!name || name === groupQuery.data?.name || rename.isPending) return;
		rename.mutate(name);
	}

	// After the group is gone for us (deleted or left), drop every cache scoped
	// to it — otherwise the 5-minute staleTime lets Back / an internal link
	// re-render the now-inaccessible group and its topics from cache instead of
	// refetching the backend 404.
	function dropGroupCaches() {
		queryClient.invalidateQueries({ queryKey: ['groups'] });
		for (const key of [
			['group', groupId],
			['members', groupId],
			['topics', groupId],
			['topic-dates', groupId]
		]) {
			queryClient.removeQueries({ queryKey: key });
		}
		// Topic detail (['topic', topicId]) and chat history (['messages',
		// chatroomId]) aren't keyed by groupId, so the group-prefix purge above
		// can't reach them. We can't enumerate this group's topic/chatroom ids
		// from here, so drop those caches wholesale — a rare, destructive action
		// where a few extra refetches for other groups are acceptable.
		queryClient.removeQueries({ queryKey: ['topic'] });
		queryClient.removeQueries({ queryKey: ['messages'] });
	}

	// --- Delete group (owner only) ---
	let deleteDialog = $state<HTMLDialogElement | null>(null);

	const del = createMutation(() => ({
		mutationFn: () => deleteGroup(groupId),
		onSuccess: () => {
			dropGroupCaches();
			goto(resolve('/groups'));
		}
	}));

	// --- Leave group (non-owner) ---
	let leaveDialog = $state<HTMLDialogElement | null>(null);

	const leave = createMutation(() => ({
		mutationFn: (userId: string) => leaveGroup(groupId, userId),
		onSuccess: () => {
			dropGroupCaches();
			goto(resolve('/groups'));
		}
	}));
</script>

<div class="min-h-screen bg-base-100">
	<AppHeader>
		<div class="flex w-full items-center gap-3">
			<button
				onclick={() => goto(resolve(`/groups/${groupId}`))}
				class="btn -ml-2 btn-square btn-ghost btn-sm"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="h-5 w-5" />
			</button>
			<h1 class="text-base font-semibold text-base-content">그룹 설정</h1>
		</div>
	</AppHeader>

	<main class="mx-auto max-w-lg space-y-6 px-4 py-6">
		{#if groupQuery.isPending}
			<p class="py-8 text-center text-sm text-base-content/70">불러오는 중...</p>
		{:else if groupQuery.isError}
			<p class="py-8 text-center text-sm text-error">그룹 정보를 불러올 수 없습니다.</p>
		{:else if groupQuery.data}
			<form onsubmit={onSaveName} class="space-y-2">
				<fieldset class="fieldset" disabled={!isOwner}>
					<legend class="fieldset-legend">그룹 이름</legend>
					<div class="join w-full">
						<input
							id="group-name"
							type="text"
							bind:value={groupName}
							oninput={() => (dirty = true)}
							maxlength={128}
							required
							aria-label="그룹 이름"
							class="validator input join-item flex-1 focus:border-primary focus:outline-none!"
						/>
						<button
							type="submit"
							disabled={!groupName.trim() ||
								groupName.trim() === groupQuery.data.name ||
								rename.isPending}
							class="btn join-item shrink-0 btn-primary"
						>
							{rename.isPending ? '저장 중...' : '저장'}
						</button>
					</div>
				</fieldset>
				{#if !isOwner}
					<p class="px-1 text-xs text-base-content/50">그룹장만 이름을 수정할 수 있어요.</p>
				{/if}
				{#if rename.isError}
					<p class="px-1 text-xs text-error" role="alert">{renameErrorText(rename.error)}</p>
				{/if}
				{#if saved}
					<div class="toast toast-center toast-bottom z-50">
						<div class="alert alert-success" role="status">
							<span>저장되었어요.</span>
						</div>
					</div>
				{/if}
			</form>

			<section class="space-y-2 border-t border-base-300 pt-4">
				<h2 class="px-1 text-xs text-base-content/50">멤버십</h2>
				{#if isOwner}
					<div
						class="rounded-xl border border-base-300 bg-base-200 px-4 py-3 text-sm text-base-content/70"
					>
						소유권을 이양한 후 나갈 수 있어요.
						<a href={resolve(`/groups/${groupId}/invite`)} class="link link-primary">
							멤버 목록에서 이양하기
						</a>
					</div>
				{:else}
					<button
						onclick={() => leaveDialog?.showModal()}
						class="btn btn-block btn-outline"
						aria-label="그룹 나가기"
					>
						그룹 나가기
					</button>
				{/if}
			</section>

			{#if isOwner}
				<section class="space-y-2 border-t border-error/30 pt-4">
					<h2 class="px-1 text-xs text-error">위험 구역</h2>
					<button
						onclick={() => deleteDialog?.showModal()}
						class="btn btn-block btn-outline btn-error"
						aria-label="그룹 삭제"
					>
						그룹 삭제
					</button>
				</section>
			{/if}
		{/if}
	</main>
</div>

<dialog
	bind:this={deleteDialog}
	class="modal modal-bottom sm:modal-middle"
	aria-labelledby="delete-group-title"
	onclose={() => del.reset()}
>
	<div class="modal-box space-y-4">
		<h2 id="delete-group-title" class="text-base font-semibold text-base-content">
			그룹을 삭제할까요?
		</h2>
		<p class="text-sm text-base-content/70">
			삭제하면 이 그룹의 대화와 멤버 기록에 더 이상 접근할 수 없어요. 이 작업은 되돌릴 수 없어요.
		</p>
		{#if del.isError}
			<p class="text-xs text-error" role="alert">{deleteErrorText(del.error)}</p>
		{/if}
		<div class="modal-action gap-2">
			<button type="button" onclick={() => deleteDialog?.close()} class="btn flex-1"> 취소 </button>
			<button
				type="button"
				onclick={() => del.mutate()}
				disabled={del.isPending}
				class="btn flex-1 btn-error"
			>
				{del.isPending ? '삭제 중...' : '삭제'}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop"><button aria-label="닫기">close</button></form>
</dialog>

<dialog
	bind:this={leaveDialog}
	class="modal modal-bottom sm:modal-middle"
	aria-labelledby="leave-group-title"
	onclose={() => leave.reset()}
>
	<div class="modal-box space-y-4">
		<h2 id="leave-group-title" class="text-base font-semibold text-base-content">
			그룹을 나갈까요?
		</h2>
		<p class="text-sm text-base-content/70">
			나가면 다시 초대받기 전까지 이 그룹에 접근할 수 없어요.
		</p>
		{#if leave.isError}
			<p class="text-xs text-error" role="alert">{leaveErrorText(leave.error)}</p>
		{/if}
		<div class="modal-action gap-2">
			<button type="button" onclick={() => leaveDialog?.close()} class="btn flex-1"> 취소 </button>
			<button
				type="button"
				onclick={() => meQuery.data && leave.mutate(meQuery.data.id)}
				disabled={leave.isPending || !meQuery.data}
				class="btn flex-1 btn-error"
			>
				{leave.isPending ? '나가는 중...' : '나가기'}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop"><button aria-label="닫기">close</button></form>
</dialog>
