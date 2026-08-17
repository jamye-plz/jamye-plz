<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { joinByCode } from '$lib/api/group.api';
	import { ApiError } from '$lib/api/client';

	// Invite-link landing: redeem the code, then drop the user into the group.
	const code = $derived(page.params.code!);

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
			await goto(resolve(`/groups/${res.group_id}`), { replaceState: true });
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) {
				// Not logged in — client.ts is redirecting to /login; keep the code.
				return;
			}
			sessionStorage.removeItem('pending_invite');
			status = 'error';
			message = err instanceof ApiError ? err.detail : '초대 링크가 유효하지 않거나 만료되었어요.';
		}
	});
</script>

<main
	id="main-content"
	class="flex min-h-dvh items-center justify-center bg-base-100 px-4 py-8 md:px-6"
>
	<div
		class="elevation-1 w-full max-w-md space-y-4 rounded-xl bg-(--color-surface-raised) p-6 text-center md:p-8"
	>
		{#if status === 'joining'}
			<span class="loading mx-auto loading-lg loading-spinner" aria-hidden="true"></span>
		{/if}
		<h1 data-route-focus-target tabindex="-1" class="text-lg font-semibold text-base-content">
			{status === 'joining' ? '그룹에 입장하는 중...' : message}
		</h1>
		{#if status === 'error'}
			<a href={resolve('/groups')} class="btn rounded-lg btn-primary"> 내 그룹으로 </a>
		{/if}
	</div>
</main>
