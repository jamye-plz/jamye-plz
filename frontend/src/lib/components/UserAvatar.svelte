<script lang="ts">
	interface Props {
		url?: string | null;
		name: string | undefined;
		sizeClass?: string;
		textClass?: string;
		class?: string;
	}

	let { url, name, sizeClass = 'w-9', textClass = 'text-sm', class: extraClass = '' }: Props =
		$props();

	function initial(n: string | undefined): string {
		return n?.trim()?.[0]?.toUpperCase() ?? '?';
	}
</script>

{#if url}
	<div class="avatar {extraClass}">
		<div class="{sizeClass} rounded-full">
			<img src={url} alt={name ?? ''} />
		</div>
	</div>
{:else}
	<div class="avatar avatar-placeholder {extraClass}" aria-hidden="true">
		<div class="{sizeClass} rounded-full bg-primary/20 text-primary {textClass} font-semibold">
			{initial(name)}
		</div>
	</div>
{/if}
