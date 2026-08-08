<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import Users from '@lucide/svelte/icons/users';
	import Bell from '@lucide/svelte/icons/bell';
	import Settings from '@lucide/svelte/icons/settings';

	let { variant }: { variant: 'rail' | 'dock' } = $props();

	type NavItem = {
		path: '/groups' | '/notifications' | '/settings';
		label: string;
		icon: typeof Users;
		current: 'page' | 'location' | undefined;
		pinned?: boolean;
	};

	const routeId = $derived(page.route.id);
	const groupsCurrent = $derived<'page' | 'location' | undefined>(
		routeId === '/groups' ? 'page' : routeId?.startsWith('/groups') ? 'location' : undefined
	);

	const items = $derived<NavItem[]>([
		{
			path: '/groups',
			label: '그룹',
			icon: Users,
			current: groupsCurrent,
			pinned: false
		},
		{
			path: '/notifications',
			label: '알림',
			icon: Bell,
			current: routeId === '/notifications' ? 'page' : undefined,
			pinned: false
		},
		{
			path: '/settings',
			label: '설정',
			icon: Settings,
			current: routeId === '/settings' ? 'page' : undefined,
			pinned: true
		}
	]);
</script>

{#if variant === 'rail'}
	<aside
		id="desktop-navigation"
		class="fixed inset-y-0 left-0 z-(--z-dropdown) hidden w-[var(--rail-width)] flex-col border-r border-base-300 bg-[var(--color-surface-raised)] p-3 pt-[max(0.75rem,env(safe-area-inset-top))] pb-[max(0.75rem,env(safe-area-inset-bottom))] pl-[max(0.75rem,env(safe-area-inset-left))] lg:flex"
		aria-label="주요 탐색"
	>
		<nav class="flex flex-1 flex-col gap-1 pt-4">
			{#each items as item (item.path)}
				{@const Icon = item.icon}
				<a
					href={resolve(item.path)}
					aria-current={item.current}
					class="flex min-h-12 items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition-colors hover:bg-base-300/70
						{item.pinned ? 'mt-auto mb-4' : ''}
						{item.current
						? 'bg-[var(--color-surface-lilac)] font-semibold text-base-content hover:bg-[var(--color-surface-lilac)]'
						: 'text-[var(--color-text-muted)] hover:text-base-content'}"
				>
					<span
						class="h-5 w-1 shrink-0 rounded-full {item.current ? 'bg-primary' : 'bg-transparent'}"
						aria-hidden="true"
					></span>
					<Icon class="h-5 w-5" aria-hidden="true" />
					<span>{item.label}</span>
				</a>
			{/each}
		</nav>
	</aside>
{:else}
	<nav id="mobile-navigation" class="app-dock dock dock-md lg:hidden" aria-label="주요 탐색">
		{#each items as item (item.path)}
			{@const Icon = item.icon}
			<a
				href={resolve(item.path)}
				aria-current={item.current}
				class={item.current
					? 'dock-active font-semibold text-primary'
					: 'text-[var(--color-text-muted)]'}
			>
				<Icon class="h-5 w-5" aria-hidden="true" />
				<span class="dock-label">{item.label}</span>
			</a>
		{/each}
	</nav>
{/if}
