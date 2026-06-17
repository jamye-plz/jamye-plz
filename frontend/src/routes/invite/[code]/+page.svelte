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
		try {
			const res = await joinByCode(code);
			// replaceState so the back button doesn't return to this transient page.
			await goto(`/groups/${res.group_id}`, { replaceState: true });
		} catch (err) {
			status = 'error';
			message =
				err instanceof ApiError ? err.detail : '초대 링크가 유효하지 않거나 만료되었어요.';
		}
	});
</script>

<main class="min-h-screen flex items-center justify-center bg-background px-4">
	<div class="w-full max-w-sm text-center space-y-4">
		{#if status === 'joining'}
			<div
				class="w-8 h-8 mx-auto rounded-full border-2 border-border border-t-accent animate-spin"
				aria-hidden="true"
			></div>
			<p class="text-text-secondary text-sm">그룹에 입장하는 중...</p>
		{:else}
			<p class="text-text-primary font-medium">{message}</p>
			<a
				href="/groups"
				class="inline-block py-2.5 px-4 rounded-xl bg-accent text-white font-medium text-sm hover:bg-accent-hover transition-colors focus-visible:outline-2 focus-visible:outline-accent"
			>
				내 그룹으로
			</a>
		{/if}
	</div>
</main>
