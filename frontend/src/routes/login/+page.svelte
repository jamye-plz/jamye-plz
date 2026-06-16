<script lang="ts">
	import { getOAuthLoginUrl } from '$lib/api/auth.api';
</script>

<main class="min-h-screen flex items-center justify-center bg-background px-4">
	<div class="w-full max-w-sm space-y-8">
		<div class="text-center space-y-2">
			<h1 class="text-3xl font-bold text-text-primary">잼얘좀</h1>
			<p class="text-text-secondary text-sm">폐쇄 그룹에서 주제를 던지고 실시간으로 떠드는 공간</p>
		</div>

		<div class="space-y-3">
			<a
				href={getOAuthLoginUrl('kakao')}
				class="flex items-center justify-center w-full py-3 px-4 rounded-lg bg-[#FEE500] text-[#191919] font-medium text-sm transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-accent"
				aria-label="카카오로 로그인"
			>
				카카오로 시작하기
			</a>

			<a
				href={getOAuthLoginUrl('google')}
				class="flex items-center justify-center w-full py-3 px-4 rounded-lg bg-surface-elevated text-text-primary font-medium text-sm border border-border transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-accent"
				aria-label="구글로 로그인"
			>
				Google로 시작하기
			</a>
		</div>
	</div>
</main>
