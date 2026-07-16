<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { joinByCode } from '$lib/api/group.api';
	import { ApiError } from '$lib/api/client';

	// Invite-link landing: redeem the code, then drop the user into the group.
	const code = $derived(page.params.code);

	let status = $state<'joining' | 'error'>('joining');
	let message = $state('');

	onMount(async () => {
		// Remember the code so a logged-out user resumes here after OAuth login
		// (client.ts redirects 401 → /login → callback returns to the SPA root).
		sessionStorage.setItem('pending_invite', code);
		try {
			const res = await joinByCode(code);
			sessionStorage.removeItem('pending_invite');
			// replaceState so the back button doesn't return to this transient page.
			await goto(`/groups/${res.group_id}`, { replaceState: true });
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) {
				// Not logged in — client.ts is redirecting to /login; keep the code.
				return;
			}
			sessionStorage.removeItem('pending_invite');
			status = 'error';
			message =
				err instanceof ApiError ? err.detail : '초대 링크가 유효하지 않거나 만료되었어요.';
		}
	});
</script>

<main class="min-h-screen flex items-center justify-center bg-base-100 px-4">
	<div class="w-full max-w-sm text-center space-y-4">
		{#if status === 'joining'}
			<div
				class="w-8 h-8 mx-auto rounded-full border-2 border-base-300 border-t-primary animate-spin"
				aria-hidden="true"
			></div>
			<p class="text-base-content/70 text-sm">그룹에 입장하는 중...</p>
		{:else}
			<p class="text-base-content font-medium">{message}</p>
			<a
				href="/groups"
				class="inline-block py-2.5 px-4 rounded-xl bg-primary text-primary-content font-medium text-sm hover:bg-primary/90 transition-colors focus-visible:outline-2 focus-visible:outline-primary"
			>
				내 그룹으로
			</a>
		{/if}
	</div>
</main>
