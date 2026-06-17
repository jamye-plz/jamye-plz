<script lang="ts">
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { getMe, patchMe, logout } from '$lib/api/auth.api';

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
	function initial(name: string | undefined): string {
		return name?.trim()?.[0]?.toUpperCase() ?? '?';
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
		<h1 class="text-base font-semibold text-text-primary">내 정보</h1>
	</header>

	<main class="px-4 py-6 space-y-6 max-w-lg mx-auto">
		{#if meQuery.isPending}
			<p class="text-text-secondary text-sm text-center py-8">불러오는 중...</p>
		{:else if meQuery.isError}
			<p class="text-danger text-sm text-center py-8">정보를 불러올 수 없습니다.</p>
		{:else if meQuery.data}
			{@const me = meQuery.data}

			<section class="flex items-center gap-4">
				{#if me.avatar_url}
					<img
						src={me.avatar_url}
						alt="프로필 사진"
						class="w-16 h-16 rounded-full object-cover bg-surface-elevated"
					/>
				{:else}
					<div
						class="w-16 h-16 rounded-full bg-accent/20 text-accent flex items-center justify-center text-2xl font-semibold"
						aria-hidden="true"
					>
						{initial(me.nickname)}
					</div>
				{/if}
				<div class="min-w-0">
					<p class="font-semibold text-text-primary truncate">{me.nickname}</p>
					<p class="text-xs text-text-muted">
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
				<label for="nickname" class="text-sm font-medium text-text-secondary">닉네임</label>
				<div class="flex items-center gap-2">
					<input
						id="nickname"
						type="text"
						bind:value={nickname}
						oninput={() => (dirty = true)}
						maxlength={64}
						required
						class="flex-1 px-3 py-2.5 rounded-xl bg-surface-elevated border border-border text-text-primary placeholder:text-text-muted text-sm focus-visible:outline-2 focus-visible:outline-accent"
					/>
					<button
						type="submit"
						disabled={!nickname.trim() || nickname.trim() === me.nickname || save.isPending}
						class="shrink-0 px-4 py-2.5 rounded-xl bg-accent text-white font-medium text-sm disabled:opacity-40 transition-opacity hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
					>
						{save.isPending ? '저장 중...' : '저장'}
					</button>
				</div>
				{#if saved}
					<p class="text-xs text-success" role="status">저장되었어요.</p>
				{:else if save.isError}
					<p class="text-xs text-danger" role="alert">저장에 실패했어요. 다시 시도해 주세요.</p>
				{/if}
				<p class="text-xs text-text-muted">프로필 사진 변경은 곧 지원될 예정이에요.</p>
			</form>

			<div class="border-t border-border pt-4">
				<button
					onclick={doLogout}
					disabled={loggingOut}
					class="w-full py-3 rounded-xl border border-border text-text-secondary text-sm hover:text-danger hover:border-danger transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-accent"
				>
					{loggingOut ? '로그아웃 중...' : '로그아웃'}
				</button>
			</div>
		{/if}
	</main>
</div>
