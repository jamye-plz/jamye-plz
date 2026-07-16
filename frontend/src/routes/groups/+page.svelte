<script lang="ts">
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
	<header class="navbar sticky top-0 z-10 bg-base-100/80 backdrop-blur border-b border-base-300">
		<div class="w-full flex items-center justify-between">
			<h1 class="text-lg font-semibold text-base-content">내 그룹</h1>
			<div class="flex items-center gap-2">
				<a href="/notifications" class="btn btn-ghost btn-square btn-sm" aria-label="알림"><Bell class="w-5 h-5" /></a>
				<a href="/settings" class="btn btn-ghost btn-square btn-sm" aria-label="설정"><Settings class="w-5 h-5" /></a>
			</div>
		</div>
	</header>

	<main class="px-4 py-6 space-y-4 max-w-lg mx-auto">
		{#if groupsQuery.isPending}
			<p class="text-base-content/70 text-sm text-center py-8">불러오는 중...</p>
		{:else if groupsQuery.isError}
			<p class="text-error text-sm text-center py-8">그룹 목록을 불러올 수 없습니다.</p>
		{:else if groupsQuery.data && groupsQuery.data.length === 0}
			<div class="text-center py-16 space-y-3">
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
							class="w-full text-left px-4 py-4 rounded-xl bg-base-200 hover:bg-base-300 border border-base-300 transition-colors focus-visible:outline-2 focus-visible:outline-primary"
							aria-label={`${group.name} 그룹으로 이동`}
						>
							<div class="flex items-center justify-between">
								<span class="font-medium text-base-content">{group.name}</span>
								<span class="badge badge-ghost badge-sm">{group.member_count}/{group.max_members}명</span>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}

		<button onclick={() => createDialog?.showModal()} class="btn btn-block btn-dash" aria-label="새 그룹 만들기">
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
				<h2 id="create-group-title" class="text-base font-semibold text-base-content">새 그룹 만들기</h2>
				<form onsubmit={handleCreate} class="space-y-3">
					<fieldset class="fieldset">
						<legend class="fieldset-legend">그룹 이름</legend>
						<input
							type="text"
							bind:value={newGroupName}
							placeholder="그룹 이름"
							maxlength={50}
							required
							class="input validator w-full"
						/>
					</fieldset>
					{#if createError}
						<p class="text-xs text-error">{createError}</p>
					{/if}
					<div class="modal-action gap-2">
						<button
							type="button"
							onclick={() => createDialog?.close()}
							class="btn flex-1"
						>
							취소
						</button>
						<button
							type="submit"
							disabled={creating || !newGroupName.trim()}
							class="btn btn-primary flex-1"
						>
							{creating ? '생성 중...' : '만들기'}
						</button>
					</div>
				</form>
			</div>
			<form method="dialog" class="modal-backdrop"><button aria-label="닫기">close</button></form>
		</dialog>
	</main>
</div>
