<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listGroups, createGroup } from '$lib/api/group.api';
	import type { Group } from '$lib/types/group.types';

	const groupsQuery = createQuery(() => ({
		queryKey: ['groups'],
		queryFn: () => listGroups()
	}));

	let showCreate = $state(false);
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
			showCreate = false;
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
	<header class="sticky top-0 z-10 bg-base-100/80 backdrop-blur border-b border-base-300 px-4 py-3 flex items-center justify-between">
		<h1 class="text-lg font-semibold text-base-content">내 그룹</h1>
		<div class="flex items-center gap-2">
			<a
				href="/notifications"
				class="p-2 rounded-lg text-base-content/70 hover:text-base-content hover:bg-base-300 transition-colors"
				aria-label="알림"
			>
				🔔
			</a>
			<a
				href="/settings"
				class="p-2 rounded-lg text-base-content/70 hover:text-base-content hover:bg-base-300 transition-colors"
				aria-label="설정"
			>
				⚙️
			</a>
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
				<button
					onclick={() => (showCreate = true)}
					class="text-sm text-primary transition-colors"
				>
					첫 그룹 만들기
				</button>
			</div>
		{:else if groupsQuery.data}
			<ul class="space-y-2" role="list" aria-label="그룹 목록">
				{#each groupsQuery.data as group (group.id)}
					<li>
						<button
							onclick={() => navigateTo(group)}
							class="w-full text-left px-4 py-4 rounded-xl bg-base-200 hover:bg-base-300 border border-base-300 transition-colors focus-visible:outline-2 focus-visible:outline-primary"
							aria-label={`${group.name} 그룹으로 이동`}
						>
							<div class="flex items-center justify-between">
								<span class="font-medium text-base-content">{group.name}</span>
								<span class="text-xs text-base-content/50">{group.member_count}/{group.max_members}명</span>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}

		<button
			onclick={() => (showCreate = true)}
			class="w-full py-3 px-4 rounded-xl border border-dashed border-base-300 text-base-content/70 hover:border-primary hover:text-primary text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary"
			aria-label="새 그룹 만들기"
		>
			+ 새 그룹 만들기
		</button>

		{#if showCreate}
			<div
				role="dialog"
				aria-modal="true"
				aria-labelledby="create-group-title"
				class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 px-4 pb-8 sm:pb-0"
			>
				<div class="w-full max-w-sm bg-base-300 rounded-2xl p-6 space-y-4 border border-base-300">
					<h2 id="create-group-title" class="text-base font-semibold text-base-content">새 그룹 만들기</h2>
					<form onsubmit={handleCreate} class="space-y-3">
						<input
							type="text"
							bind:value={newGroupName}
							placeholder="그룹 이름"
							maxlength={50}
							required
							class="w-full px-3 py-2 rounded-lg bg-base-200 border border-base-300 text-base-content placeholder:text-base-content/50 focus-visible:outline-2 focus-visible:outline-primary"
						/>
						{#if createError}
							<p class="text-xs text-error">{createError}</p>
						{/if}
						<div class="flex gap-2">
							<button
								type="button"
								onclick={() => { showCreate = false; newGroupName = ''; createError = null; }}
								class="flex-1 py-2 rounded-lg bg-base-200 border border-base-300 text-base-content/70 text-sm transition-colors hover:bg-base-300"
							>
								취소
							</button>
							<button
								type="submit"
								disabled={creating || !newGroupName.trim()}
								class="flex-1 py-2 rounded-lg bg-primary text-primary-content text-sm font-medium disabled:opacity-50 transition-opacity hover:opacity-90"
							>
								{creating ? '생성 중...' : '만들기'}
							</button>
						</div>
					</form>
				</div>
			</div>
		{/if}
	</main>
</div>
