<script lang="ts">
	import { page } from '$app/state';
	import { getOAuthLoginUrl } from '$lib/api/auth.api';

	const loginError = $derived(page.url.searchParams.get('error'));
</script>

<main class="flex min-h-screen items-center justify-center bg-base-100 px-4">
	<div class="w-full max-w-sm space-y-8">
		<div class="space-y-2 text-center">
			<h1 class="text-3xl font-bold text-base-content">잼얘좀</h1>
			<p class="text-sm text-base-content/70">폐쇄 그룹에서 주제를 던지고 실시간으로 떠드는 공간</p>
		</div>

		{#if loginError}
			<p class="text-center text-sm text-error" role="alert">
				로그인에 실패했어요. 다시 시도해 주세요.
			</p>
		{/if}

		<div class="space-y-3">
			<a
				href={getOAuthLoginUrl('kakao')}
				class="btn btn-block border-0 bg-[#FEE500] text-[#191919] hover:bg-[#FEE500]/90"
				aria-label="카카오로 로그인"
			>
				카카오로 시작하기
			</a>

			<a href={getOAuthLoginUrl('google')} class="btn btn-block" aria-label="구글로 로그인">
				Google로 시작하기
			</a>
		</div>
	</div>
</main>
