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

test('route focus on main does not render a viewport-spanning outline', () => {
	const mainFocusRule = styles.match(/#main-content:focus-visible\s*\{([^}]*)\}/)?.[1];

	assert.ok(mainFocusRule, 'main must override the global focus-visible outline');
	assert.match(mainFocusRule, /outline:\s*none;/, 'route focus must remain visually neutral');
});
