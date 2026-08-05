<script lang="ts">
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import Mic from '@lucide/svelte/icons/mic';
	import Paperclip from '@lucide/svelte/icons/paperclip';
	import Square from '@lucide/svelte/icons/square';
	import X from '@lucide/svelte/icons/x';
	import { uploadChatMedia } from '$lib/api/chat.api';
	import {
		CHAT_MEDIA_MIME_TYPES,
		MAX_MEDIA_PER_MESSAGE,
		MAX_RECORDING_SECONDS,
		isVideo,
		maxBytesFor,
		type ChatMediaInput
	} from '$lib/types/chat.types';

	interface Props {
		groupId: string;
		chatroomId: string;
		connected: boolean;
		keyboardOpen: boolean;
		/**
		 * Called once uploads finished; media is [] for a text-only message.
		 * MUST report whether the frame was actually queued — a long upload can
		 * outlive the socket, and the composer only clears the draft on success.
		 */
		onsend: (body: string, media: ChatMediaInput[]) => boolean;
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

	interface VoiceClip {
		file: File;
		/** Object URL for the preview player — revoked when removed or sent. */
		previewUrl: string;
		/** Seconds, measured while recording (metadata duration on a fresh
		 *  MediaRecorder blob is unreliable — Chrome reports Infinity). */
		duration: number;
	}

	let recording = $state(false);
	// True while the getUserMedia permission prompt is open. `recording` is
	// still false then, so without this a double tap starts a second
	// getUserMedia; when both resolve, the later MediaRecorder overwrites
	// `recorder` and the FIRST stream's reference is lost — a mic that stays
	// on with nothing left pointing at it.
	let requestingMic = $state(false);
	let recordSeconds = $state(0);
	let voiceClip = $state<VoiceClip | null>(null);
	let recorder: MediaRecorder | null = null;
	let recordTimer: ReturnType<typeof setInterval> | null = null;
	// Cancel and stop share MediaRecorder.stop(); this flag tells onstop
	// whether to keep the clip or throw it away.
	let discardRecording = false;
	// Set on teardown. getUserMedia can resolve AFTER the room unmounted (the
	// permission prompt was open) — at that point `recorder` is still null, so
	// the cleanup's stopRecording() had nothing to stop, and starting now would
	// leave the mic on with no UI left to turn it off.
	let disposed = false;

	const busy = $derived(uploading || converting);
	const canSend = $derived(
		connected &&
			!busy &&
			!recording &&
			(inputText.trim().length > 0 || attachments.length > 0 || voiceClip !== null)
	);

	// One per browser family; first supported wins. Chrome/Edge take webm/opus,
	// iOS Safari only mp4 (AAC), Firefox ogg/opus.
	const RECORDER_MIME_CANDIDATES = [
		'audio/webm;codecs=opus',
		'audio/webm',
		'audio/mp4',
		'audio/ogg;codecs=opus'
	];

	function fmtSeconds(total: number): string {
		const m = Math.floor(total / 60);
		const sec = total % 60;
		return `${m}:${String(sec).padStart(2, '0')}`;
	}

	function stopRecordTimer() {
		if (recordTimer) {
			clearInterval(recordTimer);
			recordTimer = null;
		}
	}

	async function startRecording() {
		if (recording || requestingMic) return;
		errorText = '';
		if (typeof MediaRecorder === 'undefined') {
			errorText = '이 브라우저는 음성 녹음을 지원하지 않아요.';
			return;
		}
		requestingMic = true;
		let stream: MediaStream;
		try {
			stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		} catch {
			errorText = '마이크를 사용할 수 없어요. 브라우저 설정에서 권한을 허용해 주세요.';
			return;
		} finally {
			requestingMic = false;
		}
		if (disposed) {
			// Unmounted while the permission prompt was open — release the mic
			// immediately; there is no component left to stop it later.
			stream.getTracks().forEach((t) => t.stop());
			return;
		}
		const mimeType = RECORDER_MIME_CANDIDATES.find((t) => MediaRecorder.isTypeSupported(t));
		const rec = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
		const chunks: Blob[] = [];
		discardRecording = false;
		rec.ondataavailable = (e) => {
			if (e.data.size > 0) chunks.push(e.data);
		};
		rec.onstop = () => {
			// The tab indicator (red dot) only clears once the tracks stop.
			stream.getTracks().forEach((t) => t.stop());
			stopRecordTimer();
			const seconds = recordSeconds;
			recording = false;
			recordSeconds = 0;
			recorder = null;
			if (discardRecording) return;
			// Strip any codecs suffix — the server allowlist and the presign
			// signature both use the bare type.
			const contentType = (rec.mimeType || 'audio/webm').split(';')[0];
			const blob = new Blob(chunks, { type: contentType });
			if (blob.size === 0) return;
			const ext = contentType === 'audio/mp4' ? 'm4a' : contentType.split('/')[1];
			const file = new File([blob], `voice-${seconds}s.${ext}`, { type: contentType });
			voiceClip = { file, previewUrl: URL.createObjectURL(file), duration: seconds };
		};
		recorder = rec;
		recording = true;
		recordSeconds = 0;
		rec.start();
		recordTimer = setInterval(() => {
			recordSeconds += 1;
			// Hard cap: opus at voice bitrate keeps 5 min around 1 MB, and the
			// cap also bounds worker transcription time.
			if (recordSeconds >= MAX_RECORDING_SECONDS) stopRecording();
		}, 1000);
	}

	function stopRecording() {
		if (recorder && recorder.state !== 'inactive') recorder.stop();
	}

	function cancelRecording() {
		discardRecording = true;
		stopRecording();
	}

	function removeVoiceClip() {
		if (voiceClip) URL.revokeObjectURL(voiceClip.previewUrl);
		voiceClip = null;
		errorText = '';
	}

	// Leaving the room mid-recording must release the microphone — a live
	// MediaStream keeps the browser's recording indicator on.
	$effect(() => () => {
		disposed = true;
		discardRecording = true;
		stopRecording();
		if (voiceClip) URL.revokeObjectURL(voiceClip.previewUrl);
	});

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

		// Voice path: exactly one audio attachment, nothing else (server rule).
		if (voiceClip) {
			const problem = validate(voiceClip.file);
			if (problem) {
				errorText = problem;
				return;
			}
			uploading = true;
			errorText = '';
			try {
				const uploaded = await uploadChatMedia(groupId, chatroomId, voiceClip.file, {
					duration: voiceClip.duration
				});
				if (!onsend(body, [uploaded])) {
					errorText = '연결이 끊겨 전송하지 못했어요. 잠시 후 다시 시도해 주세요.';
					return;
				}
				inputText = '';
				removeVoiceClip();
			} catch {
				errorText = '음성 메시지를 업로드하지 못했어요. 다시 시도해 주세요.';
			} finally {
				uploading = false;
			}
			return;
		}

		const pending = attachments;

		if (pending.length === 0) {
			// Only drop the draft once the frame is actually on the wire.
			if (onsend(body, [])) inputText = '';
			else errorText = '연결이 끊겨 전송하지 못했어요. 잠시 후 다시 시도해 주세요.';
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
			// A 50 MiB upload can easily outlive the socket. Clearing before
			// knowing the frame was accepted would throw away the text AND revoke
			// the previews while the send silently no-ops — the user would lose
			// everything after waiting through the whole upload, with no error.
			// The objects are already in the bucket, so a retry just re-sends
			// the metadata; nothing is re-uploaded.
			if (!onsend(body, uploaded)) {
				errorText = '연결이 끊겨 전송하지 못했어요. 잠시 후 다시 시도해 주세요.';
				return;
			}
			inputText = '';
			clearAttachments();
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
		{#if voiceClip}
			<div class="mb-2 flex items-center gap-2 rounded-xl bg-base-200 px-3 py-2">
				<audio src={voiceClip.previewUrl} controls preload="metadata" class="h-10 min-w-0 flex-1"
				></audio>
				<span class="shrink-0 text-xs text-base-content/60">{fmtSeconds(voiceClip.duration)}</span>
				<button
					type="button"
					onclick={removeVoiceClip}
					disabled={busy}
					class="btn btn-square shrink-0 btn-ghost btn-sm"
					aria-label="녹음 삭제"
				>
					<X class="h-4 w-4" />
				</button>
			</div>
		{/if}

		{#if recording}
			<div class="mb-2 flex items-center gap-3 rounded-xl bg-base-200 px-3 py-2" role="status">
				<span
					class="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-error"
					aria-hidden="true"
				></span>
				<span class="text-sm text-base-content">녹음 중 {fmtSeconds(recordSeconds)}</span>
				<span class="flex-1"></span>
				<button
					type="button"
					onclick={cancelRecording}
					class="btn btn-ghost btn-sm"
					aria-label="녹음 취소"
				>
					취소
				</button>
				<button
					type="button"
					onclick={stopRecording}
					class="btn btn-error btn-sm"
					aria-label="녹음 종료"
				>
					<Square class="h-3.5 w-3.5" />
					종료
				</button>
			</div>
		{/if}

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
				disabled={busy ||
					recording ||
					voiceClip !== null ||
					attachments.length >= MAX_MEDIA_PER_MESSAGE}
				class="btn btn-square shrink-0 btn-ghost"
				aria-label="사진 또는 동영상 첨부"
			>
				<Paperclip class="h-5 w-5" />
			</button>
			<!-- Tap-to-toggle recording. Disabled with photo attachments present:
			     the server enforces that audio rides alone on a message. -->
			<button
				type="button"
				onclick={() => (recording ? stopRecording() : startRecording())}
				disabled={busy || requestingMic || voiceClip !== null || attachments.length > 0}
				class="btn btn-square shrink-0 {recording ? 'btn-error' : 'btn-ghost'}"
				aria-label={recording ? '녹음 종료' : '음성 메시지 녹음'}
				aria-pressed={recording}
			>
				<Mic class="h-5 w-5" />
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
