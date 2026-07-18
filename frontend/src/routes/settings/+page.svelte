<script lang="ts">
	import AppHeader from '$lib/components/AppHeader.svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { getMe, patchMe, logout } from '$lib/api/auth.api';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import UserAvatar from '$lib/components/UserAvatar.svelte';

	const queryClient = useQueryClient();
	const meQuery = createQuery(() => ({ queryKey: ['me'], queryFn: getMe }));

	let nickname = $state('');
	let dirty = $state(false);
	let saved = $state(false);

	// Seed the input from the loaded profile until the user starts editing.
	$effect(() => {
		if (meQuery.data && !dirty) nickname = meQuery.data.nickname;
	});

	const save = createMutation(() => ({
		mutationFn: (name: string) => patchMe({ nickname: name }),
		onSuccess: (user) => {
			queryClient.setQueryData(['me'], user);
			dirty = false;
			saved = true;
			setTimeout(() => (saved = false), 1500);
		}
	}));

	function onSave(e: SubmitEvent) {
		e.preventDefault();
		const name = nickname.trim();
		if (!name || name === meQuery.data?.nickname || save.isPending) return;
		save.mutate(name);
	}

	let loggingOut = $state(false);
	async function doLogout() {
		loggingOut = true;
		try {
			await logout();
		} catch {
			// even if the call fails, drop local state and return to login
		}
		queryClient.clear();
		goto('/login');
	}

	const PROVIDER_LABEL: Record<string, string> = { kakao: '카카오', google: '구글' };
</script>

<div class="min-h-screen bg-base-100">
	<AppHeader>
		<div class="flex w-full items-center gap-3">
			<button
				onclick={() => goto('/groups')}
				class="btn btn-square btn-ghost btn-sm"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="h-5 w-5" />
			</button>
			<h1 class="text-base font-semibold text-base-content">내 정보</h1>
		</div>
	</AppHeader>

	<main class="mx-auto max-w-lg space-y-6 px-4 py-6">
		{#if meQuery.isPending}
			<p class="py-8 text-center text-sm text-base-content/70">불러오는 중...</p>
		{:else if meQuery.isError}
			<p class="py-8 text-center text-sm text-error">정보를 불러올 수 없습니다.</p>
		{:else if meQuery.data}
			{@const me = meQuery.data}

			<section class="flex items-center gap-4">
				<UserAvatar url={me.avatar_url} name={me.nickname} sizeClass="w-16" textClass="text-2xl" />
				<div class="min-w-0">
					<p class="truncate font-semibold text-base-content">{me.nickname}</p>
					<p class="text-xs text-base-content/50">
						{PROVIDER_LABEL[me.provider] ?? me.provider} 로그인 ·
						{new Date(me.created_at).toLocaleDateString('ko-KR', {
							year: 'numeric',
							month: 'long',
							day: 'numeric'
						})} 가입
					</p>
				</div>
			</section>

			<form onsubmit={onSave} class="space-y-2">
				<fieldset class="fieldset">
					<legend class="fieldset-legend">닉네임</legend>
					<div class="join w-full">
						<input
							id="nickname"
							type="text"
							bind:value={nickname}
							oninput={() => (dirty = true)}
							maxlength={64}
							required
							aria-label="닉네임"
							class="validator input join-item flex-1 focus:border-primary focus:outline-none!"
						/>
						<button
							type="submit"
							disabled={!nickname.trim() || nickname.trim() === me.nickname || save.isPending}
							class="btn join-item shrink-0 btn-primary"
						>
							{save.isPending ? '저장 중...' : '저장'}
						</button>
					</div>
				</fieldset>
				{#if save.isError}
					<p class="text-xs text-error" role="alert">저장에 실패했어요. 다시 시도해 주세요.</p>
				{/if}
				{#if saved}
					<div class="toast toast-center toast-bottom z-50">
						<div class="alert alert-success" role="status">
							<span>저장되었어요.</span>
						</div>
					</div>
				{/if}
				<p class="text-xs text-base-content/50">프로필 사진 변경은 곧 지원될 예정이에요.</p>
			</form>

			<div class="border-t border-base-300 pt-4">
				<button
					onclick={doLogout}
					disabled={loggingOut}
					class="btn btn-block btn-outline btn-error"
				>
					{loggingOut ? '로그아웃 중...' : '로그아웃'}
				</button>
			</div>
		{/if}
	</main>
</div>
