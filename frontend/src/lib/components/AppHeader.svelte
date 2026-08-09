<script lang="ts">
	import type { Snippet } from 'svelte';

	// The single source of truth for every screen's top bar shell. Owns the sticky
	// navbar chrome and the device safe-area insets (notch top + left/right edges) so
	// all headers line up identically. Each screen supplies its own inner row (back
	// button, title, actions) as children — only the layout of that row varies.
	let { children }: { children: Snippet } = $props();
</script>

<!--
  Outer header: full-width sticky shell that owns safe-area insets and the
  backdrop treatment. Inner div: centered to ≤720px, 56px content height.
  z-(--z-sticky) = 20; backdrop-blur capped at 8px per design contract.
-->
<header
	class="sticky top-0 z-(--z-sticky) shrink-0 border-b border-base-300 bg-base-100/95 pt-[env(safe-area-inset-top)] backdrop-blur"
>
	<div
		class="navbar mx-auto h-14 min-h-0 w-full max-w-[720px] pr-[max(1rem,env(safe-area-inset-right))] pl-[max(1rem,env(safe-area-inset-left))] md:pr-[max(1.5rem,env(safe-area-inset-right))] md:pl-[max(1.5rem,env(safe-area-inset-left))]"
	>
		{@render children()}
	</div>
</header>
