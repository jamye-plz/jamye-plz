<script lang="ts">
	import type { Snippet } from 'svelte';

	// The single source of truth for every screen's top bar shell. Owns the sticky
	// navbar chrome and the device safe-area insets (notch top + left/right edges) so
	// all headers line up identically. Each screen supplies its own inner row (back
	// button, title, actions) as children — only the layout of that row varies.
	let { children }: { children: Snippet } = $props();
</script>

<header
	class="navbar sticky top-0 z-10 shrink-0 border-b border-base-300 bg-base-100/80 pt-[env(safe-area-inset-top)] pr-[max(0.75rem,env(safe-area-inset-right))] pl-[max(0.75rem,env(safe-area-inset-left))] backdrop-blur"
>
	{@render children()}
</header>
