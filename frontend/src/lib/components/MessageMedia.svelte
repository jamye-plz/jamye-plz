<script lang="ts">
	import { isAudio, isVideo, type ChatMedia, type PendingMedia } from '$lib/types/chat.types';

	interface Props {
		/** Real attachments with signed URLs. Empty/omitted while `pending` is set. */
		media?: ChatMedia[];
		/** Placeholders for a message still awaiting its ack. */
		pending?: PendingMedia[];
		/** Open the fullscreen viewer at this item. Omit to disable tap-to-open. */
		onopen?: (index: number) => void;
		/**
		 * Report the attachment whose URL stopped working so the parent can
		 * reissue just that one. Signatures last 10 minutes while a chat stays
		 * open for hours, so this WILL fire in normal use.
		 */
		onexpired?: (mediaId: string) => void;
		/**
		 * Report that an attachment actually rendered. This — not a 200 from the
		 * refresh endpoint — is the only proof a reissued URL was any good, since
		 * the endpoint signs from the DB row and happily returns a URL for an
		 * object that is no longer in the bucket.
		 */
		onloaded?: (mediaId: string) => void;
	}

	const { media = [], pending = [], onopen, onexpired, onloaded }: Props = $props();

	// Ask at most once per URL: re-arms when that attachment's URL actually
	// changes, so a long session recovers from repeated expiry. The parent caps
	// CONSECUTIVE failed refreshes, which is what stops a genuinely missing
	// object from looping error → refresh → error.
	let askedFor = $state<Record<string, string>>({});

	// Urls that finished decoding — everything else shows a skeleton, so a slow
	// image reserves its space instead of popping in and shoving the log around.
	let loaded = $state<Record<string, boolean>>({});

	function handleLoad(item: ChatMedia) {
		loaded[item.url] = true;
		onloaded?.(item.id);
	}

	function handleError(item: ChatMedia) {
		delete loaded[item.url];
		if (!onexpired || askedFor[item.id] === item.url) return;
		askedFor[item.id] = item.url;
		onexpired(item.id);
	}

	function gridClass(count: number): string {
		return count === 1 ? 'grid-cols-1' : 'grid-cols-2';
	}

	/** Keep the skeleton the same shape as the incoming picture when we know it. */
	function ratio(width?: number | null, height?: number | null): string {
		return width && height ? `aspect-ratio:${width}/${height}` : 'min-height:10rem';
	}
</script>

{#if pending.length > 0}
	<!-- Uploaded, waiting for the server ack to hand back signed read URLs. -->
	<div class="mb-1 grid max-w-xs gap-1 {gridClass(pending.length)}">
		{#each pending as item, i (i)}
			<div
				class="flex w-full skeleton items-center justify-center rounded-sm"
				style={item.content_type.startsWith('audio/')
					? 'height:3.5rem'
					: ratio(item.width, item.height)}
				role="status"
				aria-label="전송 중"
			>
				<span class="loading loading-sm loading-spinner text-[var(--color-text-muted)]"></span>
			</div>
		{/each}
	</div>
{:else if media.length > 0}
	<div class="mb-1 grid max-w-xs gap-1 {gridClass(media.length)}">
		{#each media as item, i (item.id)}
			<div class="relative w-full overflow-hidden rounded-sm">
				{#if !loaded[item.url] && !isAudio(item.content_type)}
					<div
						class="absolute inset-0 flex skeleton items-center justify-center"
						style={ratio(item.width, item.height)}
						role="status"
						aria-label="불러오는 중"
					>
						<span class="loading loading-sm loading-spinner text-[var(--color-text-muted)]"></span>
					</div>
				{/if}
				{#if isAudio(item.content_type)}
					<!--
						Voice message: compact player + async transcript. No skeleton —
						an <audio> element has no intrinsic frame to reserve; browsers
						render controls immediately while metadata streams in.
					-->
					<div class="w-64 max-w-full rounded-lg bg-base-200 p-2">
						<audio
							src={item.url}
							controls
							preload="metadata"
							onerror={() => handleError(item)}
							onloadedmetadata={() => handleLoad(item)}
							class="h-10 w-full"
							aria-label="음성 메시지"
						></audio>
						{#if item.transcript_status === 'pending'}
							<p
								class="mt-1 flex items-center gap-1.5 px-1 text-xs text-[var(--color-text-muted)]"
								role="status"
							>
								<span class="loading loading-xs loading-spinner"></span>
								받아쓰는 중...
							</p>
						{:else if item.transcript_status === 'done' && item.transcript}
							<p class="mt-1 px-1 text-xs break-keep text-[var(--color-text-muted)]">
								{item.transcript}
							</p>
						{:else if item.transcript_status === 'failed'}
							<p class="mt-1 px-1 text-xs text-[var(--color-text-muted)]">받아쓰기에 실패했어요</p>
						{/if}
					</div>
				{:else if isVideo(item.content_type)}
					<!--
						Skeleton lifts on `loadedmetadata`, NOT `loadeddata`: with
						preload="metadata" a browser may never fetch a frame until
						playback starts, and the video sits invisible under the skeleton
						until this fires — so waiting for frame data deadlocks, with no
						visible controls to press play with. Metadata is also the moment
						dimensions are known, which is all the skeleton reserved space for.
					-->
					<!-- svelte-ignore a11y_media_has_caption -->
					<video
						src={item.url}
						controls
						preload="metadata"
						playsinline
						onloadedmetadata={() => handleLoad(item)}
						onerror={() => handleError(item)}
						class="w-full rounded-sm bg-base-300 {loaded[item.url] ? '' : 'invisible'}"
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
						class="focus-ring-inset block w-full cursor-zoom-in rounded-sm disabled:cursor-default"
						aria-label="첨부 이미지 크게 보기"
					>
						<img
							src={item.url}
							alt="첨부 이미지"
							width={item.width ?? undefined}
							height={item.height ?? undefined}
							onload={() => handleLoad(item)}
							onerror={() => handleError(item)}
							loading="lazy"
							class="max-h-64 w-full rounded-sm bg-base-300 object-cover {loaded[item.url]
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
