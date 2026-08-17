<script lang="ts">
	import { page } from '$app/state';
	import { getOAuthLoginUrl } from '$lib/api/auth.api';

	const loginError = $derived(page.url.searchParams.get('error'));
</script>

<main
	id="main-content"
	class="flex min-h-dvh items-center justify-center bg-base-100 px-4 py-8 md:px-6"
>
	<div
		class="elevation-1 w-full max-w-md space-y-8 rounded-xl bg-[var(--color-surface-raised)] p-6 md:p-8"
	>
		<div class="space-y-2 rounded-lg bg-[var(--color-surface-blush)] p-4 text-center">
			<h1 data-route-focus-target tabindex="-1" class="text-3xl font-bold text-base-content">
				잼얘좀
			</h1>
			<p class="text-base leading-relaxed text-base-content">
				폐쇄 그룹에서 주제를 던지고 실시간으로 떠드는 공간
			</p>
		</div>

		{#if loginError}
			<div class="alert alert-error" role="alert">
				<span>로그인에 실패했어요. 다시 시도해 주세요.</span>
			</div>
		{/if}

		<div class="space-y-3">
			<!-- eslint-disable svelte/no-navigation-without-resolve -- OAuth endpoints proxied to backend (/api/auth/*), not app routes -->
			<a
				href={getOAuthLoginUrl('kakao')}
				class="btn btn-block border-0 bg-[#FEE500] text-[#191919] hover:bg-[#FEE500]/90"
				aria-label="카카오로 로그인"
			>
				카카오로 시작하기
			</a>

			<a
				href={getOAuthLoginUrl('google')}
				class="btn btn-block btn-outline"
				aria-label="구글로 로그인"
			>
				구글로 시작하기
			</a>
			<!-- eslint-enable svelte/no-navigation-without-resolve -->
		</div>
	</div>
</main>
