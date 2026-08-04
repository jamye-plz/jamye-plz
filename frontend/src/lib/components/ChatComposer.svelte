<script lang="ts">
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import Paperclip from '@lucide/svelte/icons/paperclip';
	import X from '@lucide/svelte/icons/x';
	import { uploadChatMedia } from '$lib/api/chat.api';
	import {
		CHAT_MEDIA_MIME_TYPES,
		MAX_MEDIA_PER_MESSAGE,
		isVideo,
		maxBytesFor,
		type ChatMediaInput
	} from '$lib/types/chat.types';

	interface Props {
		groupId: string;
		chatroomId: string;
		connected: boolean;
		keyboardOpen: boolean;
		/** Called once uploads finished; media is [] for a text-only message. */
		onsend: (body: string, media: ChatMediaInput[]) => void;
		oninput?: () => void;
	}

	const { groupId, chatroomId, connected, keyboardOpen, onsend, oninput }: Props = $props();

	interface Attachment {
		file: File;
		/** Object URL for the local preview — revoked when removed or sent. */
		previewUrl: string;
	}

	let inputText = $state('');
	let attachments = $state<Attachment[]>([]);
	let uploading = $state(false);
	let converting = $state(false);
	let errorText = $state('');
	let fileInput = $state<HTMLInputElement | null>(null);
	let inputEl = $state<HTMLTextAreaElement | null>(null);

	const busy = $derived(uploading || converting);
	const canSend = $derived(
		connected && !busy && (inputText.trim().length > 0 || attachments.length > 0)
	);

	function humanSize(bytes: number): string {
		return `${Math.round(bytes / (1024 * 1024))}MB`;
	}

	function validate(file: File): string | null {
		if (!CHAT_MEDIA_MIME_TYPES.includes(file.type)) {
			return `${file.name}: 지원하지 않는 형식이에요. 사진 또는 mp4 동영상만 보낼 수 있어요.`;
		}
		const cap = maxBytesFor(file.type);
		if (file.size > cap) {
			return `${file.name}: 파일이 너무 커요 (최대 ${humanSize(cap)}).`;
		}
		return null;
	}

	/**
	 * iPhone photos are HEIC. iOS Safari usually transcodes to JPEG when handing
	 * a file to `<input type="file">`, but it does NOT always (Files-app picks,
	 * some iOS versions), and non-Safari browsers cannot render HEIC at all — so
	 * a HEIC that slipped through would upload fine and then show as a broken
	 * image for every recipient.
	 *
	 * Detect by file HEADER, not `file.type`: HEIC often arrives with an empty
	 * or wrong MIME, which is exactly the case a MIME check would miss.
	 *
	 * The decoder is a WASM blob, so it is imported lazily — the common
	 * JPEG/PNG path never pays for it.
	 */
	async function toSupportedImage(file: File): Promise<File> {
		let heic: typeof import('heic-to');
		try {
			heic = await import('heic-to');
		} catch {
			return file; // decoder unavailable — fall through to normal validation
		}
		if (!(await heic.isHeic(file))) return file;

		const converted = await heic.heicTo({ blob: file, type: 'image/jpeg', quality: 0.85 });
		const blob = Array.isArray(converted) ? converted[0] : converted;
		return new File([blob], file.name.replace(/\.(heic|heif)$/i, '') + '.jpg', {
			type: 'image/jpeg',
			lastModified: file.lastModified
		});
	}

	async function onPickFiles(e: Event) {
		const target = e.currentTarget as HTMLInputElement;
		const picked = Array.from(target.files ?? []);
		// Reset immediately so picking the same file twice in a row still fires.
		target.value = '';
		if (picked.length === 0) return;

		errorText = '';
		const room = MAX_MEDIA_PER_MESSAGE - attachments.length;
		if (picked.length > room) {
			errorText = `한 번에 최대 ${MAX_MEDIA_PER_MESSAGE}개까지 첨부할 수 있어요.`;
		}

		converting = true;
		try {
			for (const original of picked.slice(0, Math.max(room, 0))) {
				let file = original;
				try {
					file = await toSupportedImage(original);
				} catch {
					errorText = `${original.name}: 사진을 변환하지 못했어요.`;
					continue;
				}
				// Validate the FINAL bytes: conversion changes both type and size.
				const problem = validate(file);
				if (problem) {
					errorText = problem;
					continue;
				}
				attachments = [...attachments, { file, previewUrl: URL.createObjectURL(file) }];
			}
		} finally {
			converting = false;
		}
	}

	function removeAt(index: number) {
		const [removed] = attachments.splice(index, 1);
		if (removed) URL.revokeObjectURL(removed.previewUrl);
		attachments = [...attachments];
		errorText = '';
	}

	function clearAttachments() {
		for (const a of attachments) URL.revokeObjectURL(a.previewUrl);
		attachments = [];
	}

	/**
	 * Read intrinsic dimensions so the bubble can reserve space before load.
	 *
	 * Always resolves: dimensions are a nice-to-have, and a file the decoder
	 * neither loads nor errors on (some malformed videos do exactly that) must
	 * not strand the send button on a spinner forever.
	 */
	function probe(a: Attachment): Promise<{ width?: number; height?: number; duration?: number }> {
		return new Promise((resolve) => {
			const done = (v: { width?: number; height?: number; duration?: number }) => {
				clearTimeout(timer);
				resolve(v);
			};
			const timer = setTimeout(() => resolve({}), 5000);
			if (isVideo(a.file.type)) {
				const v = document.createElement('video');
				v.preload = 'metadata';
				v.onloadedmetadata = () =>
					done({
						width: v.videoWidth || undefined,
						height: v.videoHeight || undefined,
						duration: Number.isFinite(v.duration) ? Math.round(v.duration) : undefined
					});
				v.onerror = () => done({});
				v.src = a.previewUrl;
			} else {
				const img = new Image();
				img.onload = () => done({ width: img.naturalWidth, height: img.naturalHeight });
				img.onerror = () => done({});
				img.src = a.previewUrl;
			}
		});
	}

	async function send() {
		if (!canSend) return;
		const body = inputText.trim();
		const pending = attachments;

		if (pending.length === 0) {
			inputText = '';
			onsend(body, []);
			return;
		}

		uploading = true;
		errorText = '';
		try {
			// All-or-nothing: a partially uploaded set would either drop pictures
			// silently or leave the user unsure what was sent. Keep the
			// attachments on failure so they can just press send again.
			const uploaded: ChatMediaInput[] = [];
			for (const a of pending) {
				const dims = await probe(a);
				uploaded.push(await uploadChatMedia(groupId, chatroomId, a.file, dims));
			}
			inputText = '';
			clearAttachments();
			onsend(body, uploaded);
		} catch {
			errorText = '첨부 파일을 업로드하지 못했어요. 다시 시도해 주세요.';
		} finally {
			uploading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		// Ignore Enter while an IME composition is active (Korean/Japanese/Chinese):
		// that Enter commits the composition, and sending on it duplicates the last
		// syllable (e.g. "안녕" sent, then the committed "녕" sent again). The next,
		// non-composing Enter is the real send.
		if (e.isComposing || e.keyCode === 229) return;
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			send();
		}
	}

	// Auto-grow the textarea with its content (up to ~6 lines, then it scrolls).
	$effect(() => {
		const el = inputEl;
		if (!el) return;
		void inputText;
		el.style.height = 'auto';
		el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
	});
</script>

<footer
	class="shrink-0 border-t border-base-300 bg-base-100 px-4 pt-3 {keyboardOpen
		? 'pb-3'
		: 'pb-[calc(0.75rem+env(safe-area-inset-bottom))]'}"
>
	<div class="mx-auto max-w-2xl">
		{#if attachments.length > 0}
			<div class="mb-2 flex flex-wrap gap-2">
				{#each attachments as a, i (a.previewUrl)}
					<div class="relative">
						{#if isVideo(a.file.type)}
							<video
								src={a.previewUrl}
								muted
								preload="metadata"
								class="h-16 w-16 rounded-lg bg-base-300 object-cover"
							></video>
						{:else}
							<img
								src={a.previewUrl}
								alt="첨부 미리보기"
								class="h-16 w-16 rounded-lg bg-base-300 object-cover"
							/>
						{/if}
						<button
							type="button"
							onclick={() => removeAt(i)}
							disabled={busy}
							class="btn absolute -top-1.5 -right-1.5 btn-circle btn-neutral btn-xs"
							aria-label="첨부 제거"
						>
							<X class="h-3 w-3" />
						</button>
					</div>
				{/each}
			</div>
		{/if}

		{#if converting}
			<p class="mb-2 flex items-center gap-2 px-1 text-xs text-base-content/60" role="status">
				<span class="loading loading-xs loading-spinner"></span>
				사진을 변환하는 중이에요...
			</p>
		{:else if errorText}
			<p class="mb-2 px-1 text-xs text-error" role="alert">{errorText}</p>
		{/if}

		<div class="flex items-end gap-2">
			<input
				bind:this={fileInput}
				type="file"
				accept="image/*,video/mp4"
				multiple
				onchange={onPickFiles}
				class="hidden"
				tabindex="-1"
				aria-hidden="true"
			/>
			<button
				type="button"
				onclick={() => fileInput?.click()}
				disabled={busy || attachments.length >= MAX_MEDIA_PER_MESSAGE}
				class="btn btn-square shrink-0 btn-ghost"
				aria-label="사진 또는 동영상 첨부"
			>
				<Paperclip class="h-5 w-5" />
			</button>
			<textarea
				bind:this={inputEl}
				bind:value={inputText}
				onkeydown={handleKeydown}
				oninput={() => oninput?.()}
				placeholder="메시지 입력..."
				rows={1}
				disabled={busy}
				class="textarea max-h-40 min-h-0 flex-1 resize-none overflow-y-auto focus:border-primary focus:outline-none!"
				aria-label="메시지 입력"></textarea>
			<button
				onclick={send}
				disabled={!canSend}
				class="btn btn-square shrink-0 btn-primary"
				aria-label={busy ? '처리 중' : '메시지 보내기'}
			>
				{#if busy}
					<span class="loading loading-xs loading-spinner"></span>
				{:else}
					<ArrowUp class="h-5 w-5" />
				{/if}
			</button>
		</div>
	</div>
</footer>
