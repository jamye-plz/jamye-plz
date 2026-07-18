<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listGroups, createGroup } from '$lib/api/group.api';
	import type { Group } from '$lib/types/group.types';
	import Bell from '@lucide/svelte/icons/bell';
	import Settings from '@lucide/svelte/icons/settings';

	const groupsQuery = createQuery(() => ({
		queryKey: ['groups'],
		queryFn: () => listGroups()
	}));

	let createDialog = $state<HTMLDialogElement | null>(null);
	let newGroupName = $state('');
	let creating = $state(false);
	let createError = $state<string | null>(null);

	async function handleCreate(e: Event) {
		e.preventDefault();
		if (!newGroupName.trim()) return;
		creating = true;
		createError = null;
		try {
			const group = await createGroup(newGroupName.trim());
			createDialog?.close();
			newGroupName = '';
			goto(`/groups/${group.id}`);
		} catch (err) {
			createError = err instanceof Error ? err.message : '그룹 생성에 실패했습니다.';
		} finally {
			creating = false;
		}
	}

	function navigateTo(group: Group) {
		goto(`/groups/${group.id}`);
	}
</script>

<div class="min-h-screen bg-base-100">
	<AppHeader>
		<div class="flex w-full items-center justify-between">
			<h1 class="text-lg font-semibold text-base-content">내 그룹</h1>
			<div class="flex items-center gap-2">
				<a href="/notifications" class="btn btn-square btn-ghost btn-sm" aria-label="알림"
					><Bell class="h-5 w-5" /></a
				>
				<a href="/settings" class="btn btn-square btn-ghost btn-sm" aria-label="설정"
					><Settings class="h-5 w-5" /></a
				>
			</div>
		</div>
	</AppHeader>

	<main class="mx-auto max-w-lg space-y-4 px-4 py-6">
		{#if groupsQuery.isPending}
			<p class="py-8 text-center text-sm text-base-content/70">불러오는 중...</p>
		{:else if groupsQuery.isError}
			<p class="py-8 text-center text-sm text-error">그룹 목록을 불러올 수 없습니다.</p>
		{:else if groupsQuery.data && groupsQuery.data.length === 0}
			<div class="space-y-3 py-16 text-center">
				<p class="text-base-content/50">아직 속한 그룹이 없어요</p>
				<button onclick={() => createDialog?.showModal()} class="btn btn-link">
					첫 그룹 만들기
				</button>
			</div>
		{:else if groupsQuery.data}
			<ul class="list gap-2" role="list" aria-label="그룹 목록">
				{#each groupsQuery.data as group (group.id)}
					<li class="list-row p-0">
						<button
							onclick={() => navigateTo(group)}
							class="list-col-grow w-full rounded-xl border border-base-300 bg-base-200 px-4 py-4 text-left transition-colors hover:bg-base-300 focus-visible:outline-2 focus-visible:outline-primary"
						>
							<div class="flex items-center justify-between">
								<span class="font-medium text-base-content">{group.name}</span>
								<span class="badge badge-ghost badge-sm"
									>{group.member_count}/{group.max_members}명</span
								>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}

		<button
			onclick={() => createDialog?.showModal()}
			class="btn btn-block btn-dash"
			aria-label="새 그룹 만들기"
		>
			+ 새 그룹 만들기
		</button>

		<dialog
			bind:this={createDialog}
			class="modal modal-bottom sm:modal-middle"
			aria-labelledby="create-group-title"
			onclose={() => {
				newGroupName = '';
				createError = null;
			}}
		>
			<div class="modal-box space-y-4">
				<h2 id="create-group-title" class="text-base font-semibold text-base-content">
					새 그룹 만들기
				</h2>
				<form onsubmit={handleCreate} class="space-y-3">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">그룹 이름</legend>
						<input
							type="text"
							bind:value={newGroupName}
							placeholder="그룹 이름"
							maxlength={50}
							required
							class="validator input w-full focus:border-primary focus:outline-none!"
						/>
					</fieldset>
					{#if createError}
						<p class="text-xs text-error">{createError}</p>
					{/if}
					<div class="modal-action gap-2">
						<button type="button" onclick={() => createDialog?.close()} class="btn flex-1">
							취소
						</button>
						<button
							type="submit"
							disabled={creating || !newGroupName.trim()}
							class="btn flex-1 btn-primary"
						>
							{creating ? '생성 중...' : '만들기'}
						</button>
					</div>
				</form>
			</div>
			<form method="dialog" class="modal-backdrop">
				<button aria-label="닫기">close</button>
			</form>
		</dialog>
	</main>
</div>
