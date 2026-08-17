import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const pages = [
	['groups', readFileSync(new URL('../src/routes/groups/+page.svelte', import.meta.url), 'utf8')],
	[
		'notifications',
		readFileSync(new URL('../src/routes/notifications/+page.svelte', import.meta.url), 'utf8')
	]
];
const daisyListStyles = readFileSync(
	new URL('../node_modules/daisyui/components/list.css', import.meta.url),
	'utf8'
);
const groupSource = pages.find(([pageName]) => pageName === 'groups')[1];

function firstChildClasses(source) {
	return [
		...source.matchAll(
			/<li class="[^"]*\blist-row\b[^"]*">\s*<(?:a|button|div)\b[\s\S]*?class="([^"]*)"/g
		)
	].map(([, classes]) => classes);
}

test('single-content daisyUI list rows grow to the full row width', () => {
	assert.match(
		daisyListStyles,
		/:has\(\.list-col-grow:first-child\)\{--list-grid-cols:1fr\}/,
		'daisyUI must expose the first-column growth contract used by scan-oriented rows'
	);

	for (const [pageName, source] of pages) {
		const rows = firstChildClasses(source);
		assert.equal(rows.length, 2, `${pageName} must expose loading and interactive list rows`);
		assert.ok(
			rows.every((classes) => classes.split(/\s+/).includes('list-col-grow')),
			`${pageName} list-row first children must fill the complete row`
		);
	}
});

test('group rows use consistent gap-separated mobile surfaces', () => {
	const lists = [...groupSource.matchAll(/<ul class="([^"]*\blist\b[^"]*)"/g)];
	assert.equal(lists.length, 2, 'loading and loaded group lists must share the same layout');
	assert.ok(
		lists.every(([, classes]) => classes.split(/\s+/).includes('gap-2')),
		'group rows must keep the design-system 8px touch spacing'
	);

	const rows = [...groupSource.matchAll(/<li class="([^"]*\blist-row\b[^"]*)"/g)];
	assert.equal(
		rows.length,
		2,
		'loading and loaded group rows must share the same surface contract'
	);
	for (const [, classes] of rows) {
		const tokens = classes.split(/\s+/);
		assert.ok(tokens.includes('after:hidden'), 'daisyUI row dividers must be disabled');
		assert.ok(!tokens.includes('border-b'), 'rounded rows must not draw a physical bottom border');
		assert.ok(
			!tokens.includes('last:border-b-0'),
			'last-row styling must not change the row shape'
		);
	}

	const linkMatch = groupSource.match(
		/<a\b[\s\S]*?href=\{resolve\(`\/groups\/\$\{group\.id\}`\)\}[\s\S]*?class="([^"]*)"/
	);
	assert.ok(linkMatch, 'group navigation must use a deep-linkable anchor');
	const linkClasses = linkMatch[1].split(/\s+/);
	for (const requiredClass of [
		'list-col-grow',
		'flex',
		'min-h-16',
		'w-full',
		'items-center',
		'touch-manipulation',
		'rounded-xl',
		'hover:bg-(--color-surface-raised)',
		'active:bg-(--color-surface-raised)'
	]) {
		assert.ok(linkClasses.includes(requiredClass), `group link must include ${requiredClass}`);
	}
	const contentMatch = groupSource.match(
		/href=\{resolve\(`\/groups\/\$\{group\.id\}`\)\}[\s\S]*?>\s*<div class="([^"]*)"/
	);
	assert.ok(contentMatch, 'group link must expose its content row');
	assert.ok(
		contentMatch[1].split(/\s+/).includes('w-full'),
		'centered group content must preserve the full row width'
	);

	assert.doesNotMatch(groupSource, /function navigateTo\b/);
	assert.match(groupSource, /max-w-\[720px\] space-y-6/);
});
