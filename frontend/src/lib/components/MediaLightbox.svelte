<script lang="ts">
	import { untrack } from 'svelte';
	import X from '@lucide/svelte/icons/x';
	import Download from '@lucide/svelte/icons/download';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { chatMediaDownloadUrl } from '$lib/api/chat.api';
	import { isVideo, type ChatMedia } from '$lib/types/chat.types';

	interface Props {
		groupId: string;
		chatroomId: string;
		items: ChatMedia[];
		/** Index to open at. */
		startIndex?: number;
		onclose: () => void;
	}

	const { groupId, chatroomId, items, startIndex = 0, onclose }: Props = $props();

	// Capture the opening index once and then own it: the viewer is mounted
	// fresh per open, and paging must not be yanked back if the prop re-renders.
	// untrack() states that intent, instead of leaving it as a warning.
	let index = $state(untrack(() => startIndex));
	const current = $derived(items[index]);
	const hasPrev = $derived(index > 0);
	const hasNext = $derived(index < items.length - 1);

	function prev() {
		if (hasPrev) index -= 1;
	}
	function next() {
		if (hasNext) index += 1;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
		else if (e.key === 'ArrowLeft') prev();
		else if (e.key === 'ArrowRight') next();
	}

	// Horizontal swipe to page, vertical swipe down to dismiss — the gestures a
	// phone user expects from a photo viewer.
	let touchStartX = 0;
	let touchStartY = 0;
	function onTouchStart(e: TouchEvent) {
		touchStartX = e.changedTouches[0].clientX;
		touchStartY = e.changedTouches[0].clientY;
	}
	function onTouchEnd(e: TouchEvent) {
		const dx = e.changedTouches[0].clientX - touchStartX;
		const dy = e.changedTouches[0].clientY - touchStartY;
		if (Math.abs(dx) > Math.abs(dy)) {
			if (dx > 60) prev();
			else if (dx < -60) next();
		} else if (dy > 80) {
			onclose();
		}
	}

	let dialogEl = $state<HTMLElement | null>(null);

	// Lock background scroll while open, and restore it on teardown.
	$effect(() => {
		const previous = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		return () => {
			document.body.style.overflow = previous;
		};
	});

	// Move focus into the dialog on open so a screen-reader/keyboard user lands
	// inside it, and so focus is not left on the thumbnail behind the overlay.
	$effect(() => {
		dialogEl?.focus();
	});
</script>

<svelte:window onkeydown={onKeydown} />

<!--
  Backdrop click closes. The stopPropagation on the media wrapper keeps a tap
  on the picture itself (or a drag while zoomed) from dismissing.
-->
<div
	bind:this={dialogEl}
	class="fixed inset-0 z-(--z-overlay) flex flex-col bg-black/95 focus:outline-none"
	role="dialog"
	aria-modal="true"
	aria-label="첨부 파일 보기"
	tabindex="-1"
	ontouchstart={onTouchStart}
	ontouchend={onTouchEnd}
>
	<div
		class="flex shrink-0 items-center justify-between px-2 pt-[calc(0.5rem+env(safe-area-inset-top))] pb-2 text-white"
	>
		<button onclick={onclose} class="btn btn-square btn-ghost" aria-label="닫기">
			<X class="h-5 w-5" />
		</button>
		<span class="text-xs opacity-70">
			{#if items.length > 1}{index + 1} / {items.length}{/if}
		</span>
		<!--
			A backend endpoint, not an app route, so resolve() cannot express it
			(it only takes app route literals) — same reason the OAuth links on
			/login carry this disable. `data-sveltekit-reload` states the intent
			explicitly: hand this click to the browser rather than the client
			router. The backend answers with a redirect to a
			Content-Disposition: attachment URL, so the file is saved and the
			page never actually navigates away.
		-->
		<!-- eslint-disable svelte/no-navigation-without-resolve -- backend API endpoint, not an app route; see above -->
		<a
			href={chatMediaDownloadUrl(groupId, chatroomId, current.id)}
			data-sveltekit-reload
			class="btn btn-square btn-ghost"
			aria-label="다운로드"
		>
			<Download class="h-5 w-5" />
		</a>
		<!-- eslint-enable svelte/no-navigation-without-resolve -->
	</div>

	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="flex min-h-0 flex-1 items-center justify-center p-2" onclick={onclose}>
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="flex max-h-full max-w-full" onclick={(e) => e.stopPropagation()}>
			{#if isVideo(current.content_type)}
				<!-- svelte-ignore a11y_media_has_caption -->
				<video src={current.url} controls autoplay playsinline class="max-h-full max-w-full">
				</video>
			{:else}
				<!--
					Native pinch-zoom: `touch-action: pinch-zoom` lets the browser
					handle the gesture, which is smoother and more familiar than
					re-implementing transforms, and keeps the swipe handlers above
					working for single-finger drags.
				-->
				<img
					src={current.url}
					alt="첨부 이미지"
					class="max-h-full max-w-full object-contain"
					style="touch-action: pinch-zoom"
				/>
			{/if}
		</div>
	</div>

	{#if items.length > 1}
		<div
			class="flex shrink-0 items-center justify-center gap-6 pb-[calc(1rem+env(safe-area-inset-bottom))] text-white"
		>
			<button
				onclick={prev}
				disabled={!hasPrev}
				class="btn btn-circle btn-ghost disabled:opacity-30"
				aria-label="이전"
			>
				<ChevronLeft class="h-6 w-6" />
			</button>
			<button
				onclick={next}
				disabled={!hasNext}
				class="btn btn-circle btn-ghost disabled:opacity-30"
				aria-label="다음"
			>
				<ChevronRight class="h-6 w-6" />
			</button>
		</div>
	{/if}
</div>
