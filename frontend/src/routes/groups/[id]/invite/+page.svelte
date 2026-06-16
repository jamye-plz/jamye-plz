<script lang="ts">
	import { createMutation } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { createInvite } from '$lib/api/group.api';
	import { ApiError } from '$lib/api/client';

	const groupId = $derived(page.params.id);
	let copied = $state(false);

	const invite = createMutation(() => ({
		mutationFn: () => createInvite(groupId)
	}));

	async function copyCode(code: string) {
		try {
			await navigator.clipboard.writeText(code);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			// clipboard unavailable — user can still select the code manually
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
			초대 코드를 만들어 공유하면, 받은 사람이 코드로 그룹에 참여할 수 있어요.
		</p>

		<button
			onclick={() => invite.mutate()}
			disabled={invite.isPending}
			class="w-full py-3 rounded-xl bg-accent text-white font-medium text-sm disabled:opacity-40 transition-opacity hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
		>
			{invite.isPending ? '만드는 중...' : '초대 코드 만들기'}
		</button>

		{#if invite.isError}
			<p class="text-danger text-sm" role="alert">{errorText(invite.error)}</p>
		{/if}

		{#if invite.data}
			<div class="space-y-2 rounded-xl bg-surface border border-border p-4">
				<span class="text-xs text-text-muted">초대 코드</span>
				<div class="flex items-center gap-2">
					<code class="flex-1 font-mono text-base text-text-primary break-all">{invite.data.code}</code>
					<button
						onclick={() => copyCode(invite.data!.code)}
						class="shrink-0 px-3 py-1.5 rounded-lg bg-surface-elevated border border-border text-text-secondary text-sm hover:text-text-primary transition-colors focus-visible:outline-2 focus-visible:outline-accent"
					>
						{copied ? '복사됨' : '복사'}
					</button>
				</div>
			</div>
		{/if}
	</main>
</div>
