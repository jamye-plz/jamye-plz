<script lang="ts">
	import { goto } from '$app/navigation';
	import { patchMe } from '$lib/api/auth.api';

	// TODO: implement avatar upload via presign when backend is provisioned
	let nickname = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!nickname.trim()) return;
		submitting = true;
		error = null;
		try {
			await patchMe({ nickname: nickname.trim() });
			goto('/groups');
		} catch (err) {
			error = err instanceof Error ? err.message : '저장에 실패했습니다.';
		} finally {
			submitting = false;
		}
	}
</script>

<main class="min-h-screen flex items-center justify-center bg-background px-4">
	<div class="w-full max-w-sm space-y-8">
		<div class="text-center space-y-2">
			<h1 class="text-2xl font-bold text-text-primary">프로필 설정</h1>
			<p class="text-text-secondary text-sm">닉네임을 입력해 시작하세요</p>
		</div>

		<form onsubmit={handleSubmit} class="space-y-4">
			<div class="space-y-1">
				<label for="nickname" class="text-sm font-medium text-text-secondary">닉네임</label>
				<input
					id="nickname"
					type="text"
					bind:value={nickname}
					placeholder="닉네임 입력"
					maxlength={20}
					required
					class="w-full px-3 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-accent"
				/>
			</div>

			{#if error}
				<p class="text-sm text-danger">{error}</p>
			{/if}

			<button
				type="submit"
				disabled={submitting || !nickname.trim()}
				class="w-full py-3 px-4 rounded-lg bg-brand text-text-inverse font-medium text-sm disabled:opacity-50 transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-accent"
			>
				{submitting ? '저장 중...' : '시작하기'}
			</button>
		</form>
	</div>
</main>
