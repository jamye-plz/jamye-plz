<script lang="ts">
	import { tick } from 'svelte';

	// A center-locked horizontal date dial. Drag/scroll the strip, or click a date;
	// either way the dial rotates that date to the center and loads its topics.
	// Centering is a self-controlled rAF animation (not scrollIntoView/CSS-snap), so
	// rapid clicks just retarget the in-flight animation and the last click wins.
	let {
		dates,
		selected,
		today,
		onselect
	}: {
		dates: string[];
		selected: string;
		today: string;
		/** Called when the dial settles on a new date. */
		onselect: (date: string) => void;
	} = $props();

	const ITEM_W = 84; // px; fixed slot width (min-w-0 keeps it exact). Spacers are
	// calc(50% - ITEM_W/2) so any item (incl. the first/last) can reach the center.
	const VISIBLE_EACH_SIDE = 3; // dates shown on each side of the center

	// Display chronologically (oldest → today on the right). Source may be desc.
	const ordered = $derived([...dates].sort());

	let scroller = $state<HTMLElement | null>(null);
	let centerIndex = $state(0);
	let ready = $state(false); // hide until the initial date is centered (no flash)

	// Animation state. targetIndex !== null means a programmatic centering is in
	// flight — used to suppress the settle-commit and the per-tick haptic.
	let targetIndex: number | null = null;
	let animId = 0;
	let scrollRaf = 0;
	let settleTimer: ReturnType<typeof setTimeout> | null = null;
	// Native CSS scroll-snap handles swipe/drag snapping; we only turn it OFF while a
	// programmatic centering animation runs, so the two never fight.
	let snapOff = $state(false);
	// True when the selection changed because the USER positioned the dial (click /
	// drag / swipe). The effect then skips re-centering, so it can't pull a fresh
	// swipe back to the just-committed date.
	let selfCommit = false;

	function reduceMotion(): boolean {
		return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	}

	function subtractOneDay(yyyymmdd: string): string {
		const [y, m, d] = yyyymmdd.split('-').map(Number);
		const dt = new Date(Date.UTC(y!, m! - 1, d!));
		dt.setUTCDate(dt.getUTCDate() - 1);
		const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
		const dd = String(dt.getUTCDate()).padStart(2, '0');
		return `${dt.getUTCFullYear()}-${mm}-${dd}`;
	}

	function label(date: string): string {
		if (!today) return date;
		if (date === today) return '오늘';
		if (date === subtractOneDay(today)) return '어제';
		return date;
	}

	function clampIndex(i: number): number {
		return Math.max(0, Math.min(ordered.length - 1, i));
	}

	function nearestIndex(): number {
		if (!scroller) return 0;
		return clampIndex(Math.round(scroller.scrollLeft / ITEM_W));
	}

	function stopAnim() {
		if (animId) cancelAnimationFrame(animId);
		animId = 0;
		targetIndex = null;
		snapOff = false; // hand snapping back to the browser
	}

	function animateStep() {
		animId = 0;
		if (!scroller || targetIndex === null) return;
		const target = targetIndex * ITEM_W;
		const cur = scroller.scrollLeft;
		const diff = target - cur;
		if (Math.abs(diff) <= 0.5) {
			scroller.scrollLeft = target;
			centerIndex = clampIndex(targetIndex);
			targetIndex = null;
			snapOff = false; // restore native snapping for swipes
			return;
		}
		scroller.scrollLeft = cur + diff * 0.24; // ease toward the target
		animId = requestAnimationFrame(animateStep);
	}

	// Rotate so item `idx` is centered. smooth=false snaps instantly. Retargeting is
	// just a target swap; the running animation eases to the new index.
	function centerOnIndex(idx: number, smooth: boolean) {
		if (!scroller) return;
		idx = clampIndex(idx);
		// Already centered (uniform 84px slots make this exact) → nothing to do.
		if (Math.abs(scroller.scrollLeft - idx * ITEM_W) <= 1) {
			stopAnim();
			centerIndex = idx;
			return;
		}
		if (!smooth || reduceMotion()) {
			stopAnim();
			scroller.scrollLeft = idx * ITEM_W;
			centerIndex = idx;
			return;
		}
		snapOff = true; // disable native snap so it can't fight the animation
		targetIndex = idx;
		if (!animId) animId = requestAnimationFrame(animateStep);
	}

	function centerOnDate(date: string, smooth: boolean) {
		const idx = ordered.indexOf(date);
		if (idx >= 0) centerOnIndex(idx, smooth);
	}

	// Selecting a date: rotate to it immediately and load its topics. Rapid clicks
	// each retarget the animation, so the last click always wins.
	function pick(date: string) {
		if (!date) return;
		selfCommit = true;
		centerOnDate(date, true);
		if (date !== selected) onselect(date);
	}

	function onSettle() {
		if (targetIndex !== null || !scroller) return; // our own animation settling
		// Native scroll-snap has already aligned the strip to a date; just commit it.
		const date = ordered[nearestIndex()];
		if (date && date !== selected) {
			selfCommit = true;
			onselect(date);
		}
	}

	// Trackpad / wheel scrolling does NOT fire pointer events, so it can't go through
	// onPointerDown's stopAnim(). Cancel any in-flight centering animation here too,
	// otherwise a two-finger swipe fights the animation and feels like it's pulled
	// back. Native scroll-snap then takes over the swipe.
	function onWheel() {
		if (targetIndex !== null) stopAnim();
	}

	function onScroll() {
		if (scrollRaf) return;
		scrollRaf = requestAnimationFrame(() => {
			scrollRaf = 0;
			const i = nearestIndex();
			if (i !== centerIndex) {
				centerIndex = i;
				// tick haptic as the dial crosses into a new date (user-driven only)
				if (targetIndex === null && !reduceMotion()) navigator.vibrate?.(8);
			}
			if (settleTimer) clearTimeout(settleTimer);
			settleTimer = setTimeout(onSettle, 110);
		});
	}

	// Center on the selected date. First time: snap instantly then reveal, so
	// entering shows TODAY immediately (no oldest-date flash / rotate). Later
	// changes (click, drag, back-nav): smooth. Reads `selected` after tick so the
	// latest value wins even if it changed during the microtask.
	$effect(() => {
		selected;
		ordered;
		if (!scroller || !selected) return;
		if (ordered.indexOf(selected) < 0) return;
		if (selfCommit) {
			// The user already positioned the dial (click/drag/swipe) — don't fight
			// a fresh gesture by re-centering on the just-committed date.
			selfCommit = false;
			return;
		}
		if (!ready) {
			tick().then(() => {
				centerOnDate(selected, false);
				requestAnimationFrame(() => (ready = true));
			});
		} else {
			tick().then(() => centerOnDate(selected, true));
		}
	});

	// Mouse drag-to-scroll (touch/trackpad scroll natively). Capture only after a
	// small movement so a plain click still reaches the date button's onclick.
	const DRAG_THRESHOLD = 5;
	let dragging = $state(false);
	let pointerDown = false;
	let captured = false;
	let startX = 0;
	let startLeft = 0;
	function onPointerDown(e: PointerEvent) {
		// Any touch/click hands control to the user — stop the centering animation so
		// it doesn't fight a native touch swipe (which would otherwise be pulled back).
		stopAnim();
		if (e.pointerType !== 'mouse' || !scroller) return;
		pointerDown = true;
		captured = false;
		startX = e.clientX;
		startLeft = scroller.scrollLeft;
	}
	function onPointerMove(e: PointerEvent) {
		if (!pointerDown || !scroller) return;
		const dx = e.clientX - startX;
		if (!captured) {
			if (Math.abs(dx) < DRAG_THRESHOLD) return; // still a click, not a drag
			captured = true;
			dragging = true;
			stopAnim(); // hand scroll control to the drag
			snapOff = true; // free manual scroll; pick() snaps to center on release
			scroller.setPointerCapture(e.pointerId);
		}
		scroller.scrollLeft = startLeft - dx;
	}
	function onPointerUp(e: PointerEvent) {
		if (!pointerDown) return;
		pointerDown = false;
		if (!captured || !scroller) return; // a click → the button's onclick handles it
		captured = false;
		dragging = false;
		scroller.releasePointerCapture(e.pointerId);
		pick(ordered[nearestIndex()]); // snap exactly to center and select
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
		e.preventDefault();
		const delta = e.key === 'ArrowLeft' ? -1 : 1;
		pick(ordered[clampIndex(ordered.indexOf(selected) + delta)]);
	}

	function dist(i: number): number {
		return Math.abs(i - centerIndex);
	}
</script>

<div class="relative select-none">
	<!-- eslint-disable-next-line svelte/valid-compile -->
	<div
		bind:this={scroller}
		role="slider"
		tabindex="0"
		aria-label="날짜 선택 다이얼"
		aria-valuetext={selected ? label(selected) : ''}
		aria-valuemin={0}
		aria-valuemax={ordered.length - 1}
		aria-valuenow={centerIndex}
		onscroll={onScroll}
		onwheel={onWheel}
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onpointercancel={onPointerUp}
		onkeydown={onKeydown}
		class="flex items-stretch overflow-x-auto overscroll-x-contain py-1 outline-none transition-opacity duration-150 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden focus-visible:outline-2 focus-visible:outline-accent rounded-xl {ready
			? 'opacity-100'
			: 'opacity-0'}"
		style="scroll-snap-type: {snapOff ? 'none' : 'x mandatory'}; cursor: {dragging
			? 'grabbing'
			: 'grab'};"
	>
		<!-- leading spacer so the first date can reach the center -->
		<div class="shrink-0" style="width: calc(50% - {ITEM_W / 2}px);" aria-hidden="true"></div>

		{#each ordered as date, i (date)}
			{@const active = i === centerIndex}
			{@const hidden = dist(i) > VISIBLE_EACH_SIDE}
			<button
				type="button"
				tabindex="-1"
				data-date={date}
				onclick={() => pick(date)}
				class="shrink-0 min-w-0 snap-center flex items-center justify-center transition-[opacity,transform] duration-150"
				style="width: {ITEM_W}px; opacity: {hidden
					? 0
					: Math.max(0.35, 1 - 0.3 * dist(i))}; transform: scale({active
					? 1
					: 0.9}); pointer-events: {hidden ? 'none' : 'auto'};"
				aria-hidden={hidden}
				aria-label={label(date)}
				aria-pressed={date === selected}
			>
				<!-- The centered date is wrapped in a pill sized to its own text:
				     short labels (오늘/어제) become round, full dates a wider stadium. -->
				<span
					class="rounded-full whitespace-nowrap leading-none transition-colors {active
						? 'bg-accent text-white px-3 py-2 text-[15px] font-semibold'
						: 'px-2 py-1 text-[13px] font-medium text-text-secondary'}"
				>
					{label(date)}
				</span>
			</button>
		{/each}

		<!-- trailing spacer so the last date can reach the center -->
		<div class="shrink-0" style="width: calc(50% - {ITEM_W / 2}px);" aria-hidden="true"></div>
	</div>
</div>
