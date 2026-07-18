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

<main class="flex min-h-screen items-center justify-center bg-base-100 px-4">
	<div class="w-full max-w-sm space-y-8">
		<div class="space-y-2 text-center">
			<h1 class="text-2xl font-bold text-base-content">프로필 설정</h1>
			<p class="text-sm text-base-content/70">닉네임을 입력해 시작하세요</p>
		</div>

		<form onsubmit={handleSubmit} class="space-y-4">
			<div class="space-y-1">
				<label for="nickname" class="text-sm font-medium text-base-content/70">닉네임</label>
				<input
					id="nickname"
					type="text"
					bind:value={nickname}
					placeholder="닉네임 입력"
					maxlength={20}
					required
					class="input w-full focus:border-primary focus:outline-none!"
				/>
			</div>

			{#if error}
				<p class="text-sm text-error">{error}</p>
			{/if}

			<button
				type="submit"
				disabled={submitting || !nickname.trim()}
				class="btn btn-block btn-primary"
			>
				{submitting ? '저장 중...' : '시작하기'}
			</button>
		</form>
	</div>
</main>
