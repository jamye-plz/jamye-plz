import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import shouldMoveRouteFocus from '../src/lib/route-focus.ts';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const routesRoot = join(frontendRoot, 'src/routes');
const layoutSource = readFileSync(new URL('../src/routes/+layout.svelte', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/app.css', import.meta.url), 'utf8');
const chatRoomSource = readFileSync(
	new URL('../src/lib/components/ChatRoom.svelte', import.meta.url),
	'utf8'
);

function findRoutePages(directory) {
	return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		const path = join(directory, entry.name);
		if (entry.isDirectory()) return findRoutePages(path);
		return entry.name === '+page.svelte' ? [path] : [];
	});
}

function assertSingleFocusTarget(source, label) {
	const headings = source.match(/<h1\b[^>]*>/g) ?? [];
	const focusTargets = headings.filter(
		(heading) =>
			/\bdata-route-focus-target\b/.test(heading) && /\btabindex=(["'])-1\1/.test(heading)
	);

	assert.equal(headings.length, 1, `${label} must render exactly one h1`);
	assert.equal(
		focusTargets.length,
		1,
		`${label} h1 must be the single route focus target with tabindex=-1`
	);
}

test('route focus helper leaves app entry and query-only navigation alone', () => {
	assert.equal(shouldMoveRouteFocus({ type: 'enter' }), false, 'app entry must not steal focus');

	assert.equal(
		shouldMoveRouteFocus({
			type: 'link',
			from: {
				route: { id: '/groups/[id]' },
				url: new URL('https://jamye.example/groups/group-1?tab=topics')
			},
			to: {
				route: { id: '/groups/[id]' },
				url: new URL('https://jamye.example/groups/group-1?tab=members')
			}
		}),
		false,
		'same route and pathname query changes must preserve the active control'
	);
});

test('route focus helper moves focus for a real route navigation', () => {
	assert.equal(
		shouldMoveRouteFocus({
			type: 'link',
			from: {
				route: { id: '/groups' },
				url: new URL('https://jamye.example/groups')
			},
			to: {
				route: { id: '/settings' },
				url: new URL('https://jamye.example/settings')
			}
		}),
		true,
		'a changed route must announce the destination through its page title'
	);
});

test('layout focuses only declared page-title targets after it makes main skip-link focusable', () => {
	const callbackBody = layoutSource.match(
		/afterNavigate\(\(navigation\) => \{([\s\S]*?)\n\t\}\);/
	)?.[1];

	assert.ok(callbackBody, 'afterNavigate must own route-focus behavior');
	const mainTabindexIndex = callbackBody.indexOf("main.setAttribute('tabindex', '-1')");
	const decisionIndex = callbackBody.indexOf('shouldMoveRouteFocus(navigation)');
	const targetIndex = callbackBody.indexOf(
		"document.querySelector<HTMLElement>('[data-route-focus-target]')"
	);
	const focusIndex = callbackBody.indexOf('target.focus({ preventScroll: true });');

	assert.notEqual(mainTabindexIndex, -1, 'main must remain reachable from the skip link');
	assert.notEqual(decisionIndex, -1, 'the pure helper must decide whether focus moves');
	assert.notEqual(targetIndex, -1, 'route focus must use the declared page-title target only');
	assert.notEqual(focusIndex, -1, 'a declared page-title target must retain preventScroll focus');
	assert.ok(
		mainTabindexIndex < decisionIndex,
		'main tabindex must be set before the focus decision'
	);
	assert.ok(
		decisionIndex < targetIndex,
		'entry and query-only navigations must exit before querying a title'
	);
	assert.ok(targetIndex < focusIndex, 'the declared title must be resolved before focus moves');

	assert.doesNotMatch(
		layoutSource,
		/main\.querySelector\(/,
		'main must not be the heading search scope'
	);
	assert.doesNotMatch(
		layoutSource,
		/querySelector<HTMLElement>\(['"]h1['"]\)/,
		'generic h1 lookup is not a route contract'
	);
	assert.doesNotMatch(
		layoutSource,
		/\?\?\s*main/,
		'main must not be the fallback route-focus target'
	);
	assert.doesNotMatch(
		layoutSource,
		/pendingNavigationModality|onKeyboardInteraction|onPointerInteraction/,
		'input-modality bookkeeping must not control route focus'
	);
	assert.doesNotMatch(
		layoutSource,
		/data-route-focus(?!-target)/,
		'temporary route-focus outline markers must not return'
	);
	assert.match(
		layoutSource,
		/<a\s+href="#main-content"\s+class="skip-link">/,
		'the keyboard skip link must keep targeting the main landmark'
	);
});

test('every current main landmark and the shared chat room have one persistent h1 focus target', () => {
	const mainRoutes = findRoutePages(routesRoot).filter((path) =>
		/<main\b[^>]*\bid="main-content"/.test(readFileSync(path, 'utf8'))
	);

	assert.ok(mainRoutes.length > 0, 'the audit must cover every current main landmark route');
	for (const route of mainRoutes) {
		assertSingleFocusTarget(readFileSync(route, 'utf8'), route.replace(`${frontendRoot}/`, ''));
	}
	assertSingleFocusTarget(chatRoomSource, 'shared ChatRoom');

	const routeSources = new Map(
		mainRoutes.map((path) => [path.replace(`${routesRoot}/`, ''), readFileSync(path, 'utf8')])
	);
	for (const publicRoute of [
		'login/+page.svelte',
		'onboarding/+page.svelte',
		'invite/[code]/+page.svelte'
	]) {
		assert.ok(
			routeSources.has(publicRoute),
			`${publicRoute} must remain in the main landmark audit`
		);
	}

	const groupSource = routeSources.get('groups/[id]/+page.svelte');
	const topicSource = routeSources.get('groups/[id]/topics/[tid]/+page.svelte');
	assert.ok(groupSource, 'the async group page must be audited');
	assert.ok(topicSource, 'the async topic page must be audited');
	assert.match(
		groupSource,
		/<h1\b[^>]*data-route-focus-target[^>]*aria-label=\{groupQuery\.data\?\.name \?\? '그룹'\}[\s\S]*?\{#if groupQuery\.data\}/,
		'the group title target must persist while asynchronous group data loads'
	);
	assert.match(
		topicSource,
		/<h1\b[^>]*data-route-focus-target[^>]*aria-label=\{topicQuery\.data\?\.title \?\? '주제'\}[\s\S]*?\{#if topicQuery\.data\}/,
		'the topic title target must persist while asynchronous topic data loads'
	);
});

test('main landmark suppresses only its viewport-wide ring and exposes a compact skip-link cue', () => {
	const mainFocusRule = styles.match(/#main-content:focus-visible\s*\{([^}]*)\}/)?.[1];
	const mainCueRule = styles.match(/#main-content:focus-visible::before\s*\{([\s\S]*?)\}/)?.[1];

	assert.ok(mainFocusRule, 'main must replace its block-sized focus outline');
	assert.match(mainFocusRule, /outline:\s*none;/, 'main must not draw the viewport-wide outline');
	assert.ok(mainCueRule, 'main must provide a compact replacement focus cue');
	assert.match(
		mainCueRule,
		/content:\s*['"]메인 콘텐츠['"];/,
		'the cue must identify the landmark in Korean'
	);
	assert.match(
		mainCueRule,
		/position:\s*fixed;/,
		'the cue must not depend on main landmark geometry'
	);
	assert.match(
		mainCueRule,
		/pointer-events:\s*none;/,
		'the cue must not block content interaction'
	);
});
