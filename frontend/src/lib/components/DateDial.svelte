<script lang="ts">
	import type { EmblaCarouselType, EmblaOptionsType } from 'embla-carousel';
	import emblaCarouselSvelte from 'embla-carousel-svelte';
	import { WheelGesturesPlugin } from 'embla-carousel-wheel-gestures';

	// A center-locked horizontal date dial built on Embla Carousel. Embla owns all
	// touch/momentum/snap physics natively and emits a deterministic 'select' event
	// only once the carousel has actually settled on a snap point. That replaces the
	// old CSS scroll-snap + setTimeout(onSettle, 110) quiescence timer, which could
	// fire mid-snap with a stale nearestIndex() during iOS momentum scrolling (the
	// snap then completed with no further scroll events, leaving the visual position
	// and the committed selection diverged). Drag/scroll the strip, or click a date;
	// either way the dial rotates that date to the center and loads its topics.
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

	const VISIBLE_EACH_SIDE = 3; // dates shown on each side of the center

	// Display chronologically (oldest → today on the right). Source may be desc.
	const ordered = $derived([...dates].sort());

	// align:'center' + containScroll:false lets the first/last date reach the
	// center without manual leading/trailing spacer divs.
	const options: EmblaOptionsType = {
		align: 'center',
		containScroll: false,
		skipSnaps: false,
		dragFree: false,
		loop: false
	};
	const plugins = [WheelGesturesPlugin({ forceWheelAxis: 'x' })]; // desktop trackpad/wheel parity

	let emblaApi: EmblaCarouselType | undefined;
	let centerIndex = $state(0);
	let ready = $state(false); // hide until the initial date is centered (no flash)
	let dragging = $state(false);

	// True while a user gesture (pointer/wheel) is actively driving the carousel —
	// gates the per-tick haptic so programmatic centering never buzzes.
	let userDriven = false;
	// True while a programmatic scrollTo (init / click / external `selected` change) is
	// settling. Embla emits 'select' for programmatic moves too, so this gates
	// onEmblaSelect from committing onselect for moves the user did not make (which
	// would fire spurious selects on entry and loop on external prop changes). Cleared
	// on 'settle' and on 'pointerDown' (a real gesture always re-enables committing).
	let programmatic = false;
	// True right after a commit that already came from the user (click/drag/swipe).
	// The `selected`-tracking effect below skips re-centering in that case, so it
	// can't pull a fresh swipe back to the just-committed date and can't fire a
	// redundant onselect loop.
	let selfCommit = false;
	// Tracks the slide list's content so we only reInit() Embla when dates actually
	// change (not on every derived-array re-creation with identical content).
	let lastOrderedKey = '';

	function reduceMotion(): boolean {
		return (
			typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
		);
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

	function dist(i: number): number {
		return Math.abs(i - centerIndex);
	}

	function centerOnIndex(idx: number, jump: boolean) {
		if (!emblaApi) return;
		programmatic = true; // suppress the commit that Embla's 'select' would trigger
		emblaApi.scrollTo(clampIndex(idx), jump || reduceMotion());
	}

	function centerOnDate(date: string, jump: boolean) {
		const idx = ordered.indexOf(date);
		if (idx >= 0) centerOnIndex(idx, jump);
	}

	// Selecting a date: rotate to it immediately and load its topics. Rapid clicks
	// each retarget Embla's in-flight scroll animation, so the last click wins.
	function pick(date: string) {
		if (!date) return;
		selfCommit = true;
		centerOnDate(date, false); // programmatic → onEmblaSelect won't double-commit
		if (date !== selected) onselect(date);
	}

	// The ONLY commit point for gesture-driven selection (drag/swipe release).
	// Embla fires 'select' once the carousel has deterministically settled on a
	// snap point — unlike the old scroll-quiescence timer, it cannot fire mid-snap
	// with a stale index, which eliminates the iOS race.
	function onEmblaSelect(api: EmblaCarouselType) {
		const idx = api.selectedScrollSnap();
		centerIndex = idx;
		if (programmatic) return; // init / click / external change — not a user commit
		const date = ordered[idx];
		if (date && date !== selected) {
			selfCommit = true;
			onselect(date);
		}
	}

	// Live centered index from the scroll progress (evenly-spaced equal-width slides),
	// so the pill fade/scale tracks the drag continuously, not just when the snap flips.
	function onEmblaScroll(api: EmblaCarouselType) {
		const i = clampIndex(Math.round(api.scrollProgress() * (ordered.length - 1)));
		if (i !== centerIndex) {
			centerIndex = i;
			// tick haptic as the dial crosses into a new date (user-driven only)
			if (userDriven && !reduceMotion()) navigator.vibrate?.(8);
		}
	}

	function onInit(e: CustomEvent<EmblaCarouselType>) {
		emblaApi = e.detail;
		emblaApi.on('select', onEmblaSelect);
		emblaApi.on('scroll', onEmblaScroll);
		emblaApi.on('pointerDown', () => {
			programmatic = false; // a real gesture: let its settle commit
			userDriven = true;
			dragging = true;
		});
		emblaApi.on('pointerUp', () => {
			dragging = false;
		});
		emblaApi.on('settle', () => {
			userDriven = false;
			programmatic = false;
		});

		// First render: snap instantly to `selected` then reveal, so entering shows
		// TODAY immediately (no oldest-date flash / rotate). Marked programmatic so the
		// resulting 'select' does not fire a spurious onselect on entry.
		const idx = ordered.indexOf(selected);
		if (idx >= 0) {
			programmatic = true;
			emblaApi.scrollTo(idx, true);
			centerIndex = idx;
		}
		lastOrderedKey = ordered.join('|');
		requestAnimationFrame(() => (ready = true));
	}

	// Re-measure Embla when the slide list itself changes (e.g. the dates query
	// refetches with a new range) so scrollTo() indices stay in sync with the DOM.
	$effect(() => {
		const key = ordered.join('|');
		if (!emblaApi || !ready || key === lastOrderedKey) return;
		lastOrderedKey = key;
		emblaApi.reInit(options);
		if (selected) centerOnDate(selected, true);
	});

	// Center on the selected date whenever it changes externally (e.g. back-nav).
	// Skipped right after a user-driven commit so a fresh gesture isn't fought and
	// so we don't loop back into firing onselect again.
	$effect(() => {
		selected;
		if (!emblaApi || !selected) return;
		if (ordered.indexOf(selected) < 0) return;
		if (selfCommit) {
			selfCommit = false;
			return;
		}
		centerOnDate(selected, false);
	});

	function onKeydown(e: KeyboardEvent) {
		if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
		e.preventDefault();
		const delta = e.key === 'ArrowLeft' ? -1 : 1;
		pick(ordered[clampIndex(ordered.indexOf(selected) + delta)]);
	}
</script>

<div class="relative select-none">
	<div
		role="slider"
		tabindex="0"
		aria-label="날짜 선택 다이얼"
		aria-valuetext={selected ? label(selected) : ''}
		aria-valuemin={0}
		aria-valuemax={ordered.length - 1}
		aria-valuenow={centerIndex}
		onkeydown={onKeydown}
		use:emblaCarouselSvelte={{ options, plugins }}
		onemblaInit={onInit}
		class="[scrollbar-width:none] overflow-hidden rounded-xl py-1 transition-opacity duration-150 outline-none [-ms-overflow-style:none] focus-visible:outline-2 focus-visible:outline-primary [&::-webkit-scrollbar]:hidden {ready
			? 'opacity-100'
			: 'opacity-0'}"
		style="cursor: {dragging ? 'grabbing' : 'grab'};"
	>
		<div class="flex items-stretch">
			{#each ordered as date, i (date)}
				{@const active = i === centerIndex}
				{@const hidden = dist(i) > VISIBLE_EACH_SIDE}
				<div class="flex min-w-0 shrink-0 grow-0 basis-[112px] items-center justify-center">
					<button
						type="button"
						tabindex="-1"
						data-date={date}
						onclick={() => pick(date)}
						class="flex w-full items-center justify-center transition-[opacity,transform] duration-150"
						style="opacity: {hidden
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
							class="rounded-full leading-none whitespace-nowrap transition-colors {active
								? 'bg-primary px-3 py-2 text-[15px] font-semibold text-primary-content'
								: 'px-2 py-1 text-[13px] font-medium text-base-content/70'}"
						>
							{label(date)}
						</span>
					</button>
				</div>
			{/each}
		</div>
	</div>
</div>
