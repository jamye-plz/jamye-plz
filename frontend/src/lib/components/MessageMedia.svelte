<script lang="ts">
	import { isVideo, type ChatMedia, type PendingMedia } from '$lib/types/chat.types';

	interface Props {
		/** Real attachments with signed URLs. Empty/omitted while `pending` is set. */
		media?: ChatMedia[];
		/** Placeholders for a message still awaiting its ack. */
		pending?: PendingMedia[];
		/** Open the fullscreen viewer at this item. Omit to disable tap-to-open. */
		onopen?: (index: number) => void;
		/**
		 * Ask the parent to refetch history so expired presigned URLs are
		 * reissued. Media URLs are signed for 10 minutes but a chat stays open
		 * far longer, so this WILL fire in normal use.
		 */
		onexpired?: () => void;
	}

	const { media = [], pending = [], onopen, onexpired }: Props = $props();

	// Ask for a refresh at most once per set of URLs. Re-arms when the URLs
	// actually change, so a long session can recover from repeated expiry. The
	// parent rate-limits the refetch, which is what stops a genuinely missing
	// object from looping error → refetch → error.
	let askedFor = $state('');
	const urlKey = $derived(media.map((m) => m.url).join('|'));

	// Urls that finished decoding — everything else shows a skeleton, so a slow
	// image reserves its space instead of popping in and shoving the log around.
	let loaded = $state<Record<string, boolean>>({});

	function handleError(url: string) {
		delete loaded[url];
		if (!onexpired || askedFor === urlKey) return;
		askedFor = urlKey;
		onexpired();
	}

	function gridClass(count: number): string {
		return count === 1 ? 'grid-cols-1' : 'grid-cols-2';
	}

	/** Keep the skeleton the same shape as the incoming picture when we know it. */
	function ratio(width?: number | null, height?: number | null): string {
		return width && height ? `aspect-ratio:${width}/${height}` : 'aspect-ratio:4/3';
	}
</script>

{#if pending.length > 0}
	<!-- Uploaded, waiting for the server ack to hand back signed read URLs. -->
	<div class="mb-1 grid max-w-xs gap-1 {gridClass(pending.length)}">
		{#each pending as item, i (i)}
			<div
				class="flex w-full skeleton items-center justify-center rounded-lg"
				style={ratio(item.width, item.height)}
				role="status"
				aria-label="전송 중"
			>
				<span class="loading loading-sm loading-spinner text-base-content/40"></span>
			</div>
		{/each}
	</div>
{:else if media.length > 0}
	<div class="mb-1 grid max-w-xs gap-1 {gridClass(media.length)}">
		{#each media as item, i (item.id)}
			<div class="relative w-full overflow-hidden rounded-lg">
				{#if !loaded[item.url]}
					<div
						class="absolute inset-0 flex skeleton items-center justify-center"
						style={ratio(item.width, item.height)}
						role="status"
						aria-label="불러오는 중"
					>
						<span class="loading loading-sm loading-spinner text-base-content/40"></span>
					</div>
				{/if}
				{#if isVideo(item.content_type)}
					<!-- svelte-ignore a11y_media_has_caption -->
					<video
						src={item.url}
						controls
						preload="metadata"
						playsinline
						onloadeddata={() => (loaded[item.url] = true)}
						onerror={() => handleError(item.url)}
						class="w-full rounded-lg bg-base-300 {loaded[item.url] ? '' : 'invisible'}"
						style={loaded[item.url] ? '' : ratio(item.width, item.height)}
						aria-label="첨부 동영상"
					></video>
				{:else}
					<!--
						A button, not a bare img with onclick: the viewer must be
						reachable by keyboard and announced as activatable.
						Video is deliberately NOT wrapped — a tap there has to reach
						the native controls to play.
					-->
					<button
						type="button"
						onclick={() => onopen?.(i)}
						disabled={!onopen}
						class="block w-full cursor-zoom-in focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:cursor-default"
						aria-label="첨부 이미지 크게 보기"
					>
						<img
							src={item.url}
							alt="첨부 이미지"
							width={item.width ?? undefined}
							height={item.height ?? undefined}
							onload={() => (loaded[item.url] = true)}
							onerror={() => handleError(item.url)}
							loading="lazy"
							class="max-h-64 w-full rounded-lg bg-base-300 object-cover {loaded[item.url]
								? ''
								: 'invisible'}"
							style={loaded[item.url] ? '' : ratio(item.width, item.height)}
						/>
					</button>
				{/if}
			</div>
		{/each}
	</div>
{/if}
