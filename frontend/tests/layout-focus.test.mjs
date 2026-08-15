import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../src/routes/+layout.svelte', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/app.css', import.meta.url), 'utf8');

test('query-only navigation preserves the current focus target', () => {
	const callbackBody = source.match(
		/afterNavigate\(\(\{ from, to \}\) => \{([\s\S]*?)\n\t\}\);/
	)?.[1];

	assert.ok(callbackBody, 'afterNavigate must inspect the source and destination');
	const routeGuardIndex = callbackBody.indexOf('from.route.id === to.route.id');
	const pathGuardIndex = callbackBody.indexOf('from.url.pathname === to.url.pathname');
	const returnIndex = callbackBody.indexOf('return;');
	const focusIndex = callbackBody.indexOf('target.focus({ preventScroll: true });');

	assert.notEqual(routeGuardIndex, -1, 'same-route query updates must keep local focus');
	assert.notEqual(
		pathGuardIndex,
		-1,
		'same-path query updates must keep the active control focused'
	);
	assert.notEqual(returnIndex, -1, 'same-page navigation must exit before resetting focus');
	assert.notEqual(focusIndex, -1, 'actual page changes must still focus the main landmark');
	assert.ok(routeGuardIndex < returnIndex, 'the route check must guard the early return');
	assert.ok(pathGuardIndex < returnIndex, 'the path check must guard the early return');
	assert.ok(returnIndex < focusIndex, 'the same-page guard must run before route focus is reset');
});

test('only pointer-triggered route focus suppresses the viewport-spanning outline', () => {
	const mainFocusRule = styles.match(
		/#main-content\[data-route-focus\]:focus-visible\s*\{([^}]*)\}/
	)?.[1];

	assert.ok(mainFocusRule, 'pointer-triggered route focus must override the global outline');
	assert.match(mainFocusRule, /outline:\s*none;/, 'pointer route focus must remain neutral');
	assert.doesNotMatch(
		styles,
		/#main-content:focus-visible\s*\{/,
		'keyboard and skip-link focus must keep the global visible indicator'
	);
	assert.match(
		source,
		/window\.addEventListener\('keydown', onKeyboardInteraction, true\)/,
		'keyboard input must be tracked before route focus moves'
	);
	assert.match(
		source,
		/window\.addEventListener\('pointerdown', onPointerInteraction, true\)/,
		'pointer input must be tracked before route focus moves'
	);
	assert.match(
		source,
		/let pendingNavigationModality: 'keyboard' \| 'pointer' \| null = null/,
		'unknown navigation modality must remain distinct from pointer input'
	);
	assert.match(
		source,
		/if \(target === main && navigationModality === 'pointer'\)/,
		'only observed pointer route focus may set the suppression marker'
	);
	assert.match(
		source,
		/main\.addEventListener\('blur', \(\) => delete main\.dataset\.routeFocus, \{ once: true \}\)/,
		'the suppression marker must be removed when focus leaves main'
	);
});

test('navigation consumes the observed input modality before any early return', () => {
	const callbackBody = source.match(
		/afterNavigate\(\(\{ from, to \}\) => \{([\s\S]*?)\n\t\}\);/
	)?.[1];

	assert.ok(callbackBody, 'afterNavigate must expose its focus behavior');
	const readIndex = callbackBody.indexOf('const navigationModality = pendingNavigationModality;');
	const resetIndex = callbackBody.indexOf('pendingNavigationModality = null;');
	const returnIndex = callbackBody.indexOf('return;');

	assert.notEqual(readIndex, -1, 'navigation must read the pending modality');
	assert.notEqual(resetIndex, -1, 'navigation must reset the pending modality');
	assert.ok(readIndex < resetIndex, 'navigation must capture the modality before resetting it');
	assert.ok(resetIndex < returnIndex, 'query-only navigation must also consume the modality');
});
