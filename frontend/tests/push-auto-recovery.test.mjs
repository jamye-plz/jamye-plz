import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const pushApi = readFileSync(new URL('../src/lib/api/push.api.ts', import.meta.url), 'utf8');
const pushReconciler = readFileSync(
	new URL('../src/lib/components/PushReconciler.svelte', import.meta.url),
	'utf8'
);
const settingsPage = readFileSync(
	new URL('../src/routes/settings/+page.svelte', import.meta.url),
	'utf8'
);
const serviceWorker = readFileSync(new URL('../src/service-worker.ts', import.meta.url), 'utf8');
const pushIntent = readFileSync(new URL('../src/lib/push-intent.ts', import.meta.url), 'utf8');
const pushRecoverySignal = readFileSync(
	new URL('../src/lib/push-recovery-signal.ts', import.meta.url),
	'utf8'
);

function extractRecoverIntendedPush() {
	const fn = pushApi.match(/async function recoverIntendedPush[\s\S]*?\n}\n/)?.[0];
	assert.ok(fn, 'recoverIntendedPush must exist in push.api.ts');
	return fn;
}

function extractReclaimPushForCurrentUser() {
	const fn = pushApi.match(/export async function reclaimPushForCurrentUser[\s\S]*?\n}\n/)?.[0];
	assert.ok(fn, 'reclaimPushForCurrentUser must exist in push.api.ts');
	return fn;
}

function extractOnTogglePush() {
	const fn = settingsPage.match(/async function onTogglePush[\s\S]*?\n\t}\n/)?.[0];
	assert.ok(fn, 'onTogglePush must exist in settings/+page.svelte');
	return fn;
}

function extractTeardownRecoveredSub() {
	const fn = pushApi.match(/async function teardownRecoveredSub[\s\S]*?\n}\n/)?.[0];
	assert.ok(fn, 'teardownRecoveredSub must exist in push.api.ts');
	return fn;
}

test('reclaimPushForCurrentUser takes the current user id', () => {
	assert.ok(
		/export async function reclaimPushForCurrentUser\(userId: string\)/.test(pushApi),
		'reclaimPushForCurrentUser must accept userId: string'
	);
});

test('recovery is gated on getPushIntent() matching the current user', () => {
	const fn = extractRecoverIntendedPush();
	assert.ok(
		/if \(getPushIntent\(\) !== userId\) return;/.test(fn),
		'a marker belonging to a different user (or no marker) must be ignored'
	);
});

test('recovery only READS Notification.permission and never requests it', () => {
	const fn = extractRecoverIntendedPush();
	assert.ok(
		/if \(Notification\.permission !== 'granted'\)/.test(fn),
		'permission must be read before any subscribe attempt'
	);
	assert.doesNotMatch(
		fn,
		/requestPermission/,
		'recovery must never call requestPermission (no transient activation)'
	);
	assert.ok(
		/await requestAndSubscribe\(public_key\);/.test(fn),
		'subscribe must only be reached once permission is confirmed granted'
	);
});

test('denied/default permission removes the marker and skips the subscribe attempt', () => {
	const fn = extractRecoverIntendedPush();
	const permIdx = fn.indexOf("Notification.permission !== 'granted'");
	const clearIdx = fn.indexOf('clearPushIntent();');
	const subscribeIdx = fn.indexOf('requestAndSubscribe(public_key)');
	assert.notEqual(permIdx, -1);
	assert.notEqual(clearIdx, -1);
	assert.ok(permIdx < clearIdx, 'clearPushIntent must sit inside the non-granted branch');
	assert.ok(clearIdx < subscribeIdx, 'clearPushIntent must run before any subscribe path');
});

test('an empty VAPID key keeps the marker instead of clearing it', () => {
	const fn = extractRecoverIntendedPush();
	assert.ok(/if \(!public_key\) return;/.test(fn), 'empty key must return without clearing intent');
	const clearCalls = fn.match(/clearPushIntent\(\)/g) ?? [];
	assert.equal(
		clearCalls.length,
		2,
		'clearPushIntent must be called only from the two non-granted-permission branches'
	);
});

test('recovery failures are fully swallowed inside recoverIntendedPush', () => {
	const fn = extractRecoverIntendedPush();
	const tryIdx = fn.indexOf('try {');
	const fetchIdx = fn.indexOf('await getVapidPublicKey();');
	const subscribeIdx = fn.indexOf('await requestAndSubscribe(public_key);');
	const catchIdx = fn.indexOf('} catch {');
	assert.ok(tryIdx !== -1 && fetchIdx !== -1 && subscribeIdx !== -1 && catchIdx !== -1);
	assert.ok(tryIdx < fetchIdx, 'key fetch must run inside the try');
	assert.ok(
		fetchIdx < subscribeIdx && subscribeIdx < catchIdx,
		'subscribe must run inside the try'
	);
});

test('recovery runs on the !existing path, outside the detachPushOnLogout catch', () => {
	const fn = extractReclaimPushForCurrentUser();
	const notExistingIdx = fn.indexOf('if (!existing) {');
	const recoverIdx = fn.indexOf('await recoverIntendedPush(userId);');
	const innerTryIdx = fn.indexOf('try {', notExistingIdx);
	const detachIdx = fn.indexOf('await detachPushOnLogout();');

	assert.notEqual(notExistingIdx, -1, 'the !existing branch must still gate the new call');
	assert.notEqual(recoverIdx, -1);
	assert.notEqual(innerTryIdx, -1);
	assert.notEqual(detachIdx, -1);

	assert.ok(
		notExistingIdx < recoverIdx && recoverIdx < innerTryIdx,
		'recoverIntendedPush must run on the !existing branch, before the inner try/catch'
	);
	assert.ok(
		recoverIdx < detachIdx,
		'the recovery call must textually precede (and stay outside) the detachPushOnLogout catch'
	);
});

test('the existing reclaim/rotation/detach logic is untouched', () => {
	assert.ok(/await reconcilePush\(existing\);/.test(pushApi), 'no-key reconcile path must remain');
	assert.ok(
		/await reconcileOrRecreate\(public_key\);/.test(pushApi),
		'key-rotation resubscribe path must remain'
	);
	assert.ok(
		/export async function detachPushOnLogout\(\): Promise<void>/.test(pushApi),
		'detachPushOnLogout must remain exported and unchanged in shape'
	);
	assert.ok(
		/export function reconcilePush\(sub: PushSubscription\): Promise<void>/.test(pushApi),
		'reconcilePush signature must remain unchanged'
	);
	assert.ok(
		/export async function reconcileOrRecreate\(vapidPublicKey: string\): Promise<boolean>/.test(
			pushApi
		),
		'reconcileOrRecreate signature must remain unchanged'
	);
});

test('PushReconciler passes the user id and keeps the lastReclaimed guard', () => {
	assert.ok(
		/reclaimPushForCurrentUser\(uid\)/.test(pushReconciler),
		'PushReconciler must call reclaimPushForCurrentUser(uid)'
	);
	assert.ok(
		/uid !== lastReclaimed/.test(pushReconciler),
		'the once-per-user reclaim guard must remain'
	);
});

test('service-worker.ts never imports push-intent', () => {
	assert.doesNotMatch(
		serviceWorker,
		/push-intent/,
		'the service worker has no localStorage and must never touch the intent module'
	);
});

test('settings toggle ON success sets the intent marker', () => {
	const fn = extractOnTogglePush();
	const turnOnIdx = fn.indexOf('if (turnOn) {');
	const elseIdx = fn.indexOf('} else {');
	const setIdx = fn.indexOf('if (uid) setPushIntent(uid);');
	assert.notEqual(turnOnIdx, -1);
	assert.notEqual(elseIdx, -1);
	assert.notEqual(setIdx, -1);
	assert.ok(turnOnIdx < setIdx && setIdx < elseIdx, 'setPushIntent must run in the turnOn branch');
});

test('settings toggle OFF success clears the intent marker', () => {
	const fn = extractOnTogglePush();
	const elseIdx = fn.indexOf('} else {');
	const clearIdx = fn.indexOf('clearPushIntent();');
	assert.notEqual(elseIdx, -1);
	assert.notEqual(clearIdx, -1);
	assert.ok(elseIdx < clearIdx, 'clearPushIntent must run in the turnOff branch');
});

test('a failed toggle never reaches the marker calls (both sit before the catch)', () => {
	const fn = extractOnTogglePush();
	const catchIdx = fn.indexOf('} catch (err) {');
	const setIdx = fn.indexOf('if (uid) setPushIntent(uid);');
	const clearIdx = fn.indexOf('clearPushIntent();');
	assert.notEqual(catchIdx, -1);
	assert.ok(setIdx < catchIdx, 'setPushIntent must run before the catch, i.e. only on success');
	assert.ok(clearIdx < catchIdx, 'clearPushIntent must run before the catch, i.e. only on success');
});

test('settings onMount backfills the marker on reconcile success only when uid is resolved', () => {
	assert.match(
		settingsPage,
		/const uid = meQuery\.data\?\.id;\s*\n\s*if \(uid\) setPushIntent\(uid\);/,
		'backfill must be guarded on meQuery.data?.id, never write undefined/empty'
	);
});

test('push-intent is imported by push.api.ts and settings, never by the service worker', () => {
	assert.ok(
		/import \{ clearPushIntent, getPushIntent \} from '\$lib\/push-intent';/.test(pushApi),
		'push.api.ts must import the intent accessors it uses'
	);
	assert.ok(
		/import \{ clearPushIntent, setPushIntent \} from '\$lib\/push-intent';/.test(settingsPage),
		'settings must import the intent writers it uses'
	);
	assert.doesNotMatch(serviceWorker, /from '\$lib\/push-intent'/);
});

// --- T3b: reactive settings-toggle refresh on background recovery ---

test('push-recovery-signal.ts exports a writable pulse and a success-only publisher', () => {
	assert.ok(
		/export const pushRecoverySignal = writable\(0\);/.test(pushRecoverySignal),
		'the signal must be a plain writable store'
	);
	assert.ok(
		/export function signalPushRecovered\(\): void/.test(pushRecoverySignal),
		'signalPushRecovered must be the sole publish entry point'
	);
});

test('recoverIntendedPush re-checks intent right before subscribing (TOCTOU narrowing)', () => {
	const fn = extractRecoverIntendedPush();
	const emptyKeyIdx = fn.indexOf('if (!public_key) return;');
	const recheckMatches = [...fn.matchAll(/if \(getPushIntent\(\) !== userId\) return;/g)];
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key);');

	assert.notEqual(emptyKeyIdx, -1);
	assert.notEqual(subIdx, -1);
	assert.equal(
		recheckMatches.length,
		2,
		'getPushIntent must be re-checked twice: once at entry, once right before subscribing'
	);

	const recheckIdx = recheckMatches[1].index;
	assert.ok(
		emptyKeyIdx < recheckIdx && recheckIdx < subIdx,
		'the second intent re-check must sit between the public_key check and requestAndSubscribe'
	);
});

test('teardownRecoveredSub races a server delete against a timeout then unsubscribes', () => {
	const fn = extractTeardownRecoveredSub();
	const raceIdx = fn.indexOf('await Promise.race([');
	const serverDeleteIdx = fn.indexOf('unsubscribePush(sub.endpoint).catch(() => {})');
	const timeoutIdx = fn.indexOf('setTimeout(resolve, 3000)');
	const browserUnsubscribeIdx = fn.indexOf('await sub.unsubscribe().catch(() => {});');

	assert.notEqual(raceIdx, -1);
	assert.notEqual(serverDeleteIdx, -1);
	assert.notEqual(timeoutIdx, -1);
	assert.notEqual(browserUnsubscribeIdx, -1);
	assert.ok(
		raceIdx < serverDeleteIdx && serverDeleteIdx < timeoutIdx && timeoutIdx < browserUnsubscribeIdx,
		'must race the server delete vs a timeout, then unsubscribe locally regardless'
	);
});

test('push.api.ts imports getMe from the sibling auth.api module', () => {
	assert.ok(
		/import \{ getMe \} from '\.\/auth\.api';/.test(pushApi),
		'the identity recheck must reuse the existing /me endpoint'
	);
});

test('recoverIntendedPush signals only once subscribe, marker, and identity all confirm', () => {
	const fn = extractRecoverIntendedPush();
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key);');
	const notSubIdx = fn.indexOf('if (!sub) return;');
	const markerRecheckIdx = fn.indexOf('if (getPushIntent() !== userId) {', notSubIdx);
	const meIdx = fn.indexOf('const me = await getMe().catch(() => null);');
	const identityCheckIdx = fn.indexOf('if (!me || me.id !== userId) {');
	const signalIdx = fn.indexOf('signalPushRecovered();');

	assert.notEqual(subIdx, -1, 'the subscribe result must be captured');
	assert.notEqual(notSubIdx, -1, 'a null subscription must bail before signaling');
	assert.notEqual(markerRecheckIdx, -1, 'the post-await marker recheck must exist');
	assert.notEqual(meIdx, -1, 'identity must be re-verified with a server round trip');
	assert.notEqual(identityCheckIdx, -1, 'the identity mismatch branch must exist');
	assert.notEqual(signalIdx, -1, 'signalPushRecovered must exist');

	assert.ok(
		subIdx < notSubIdx &&
			notSubIdx < markerRecheckIdx &&
			markerRecheckIdx < meIdx &&
			meIdx < identityCheckIdx &&
			identityCheckIdx < signalIdx,
		'subscribe, the marker recheck, then identity must all pass before the pulse fires'
	);
});

test('a cross-tab toggle-OFF during requestAndSubscribe tears the subscription back down', () => {
	const fn = extractRecoverIntendedPush();
	const notSubIdx = fn.indexOf('if (!sub) return;');
	const markerRecheckIdx = fn.indexOf('if (getPushIntent() !== userId) {', notSubIdx);
	const teardownIdx = fn.indexOf('await teardownRecoveredSub(sub);', markerRecheckIdx);
	const returnIdx = fn.indexOf('return;', teardownIdx);
	const meIdx = fn.indexOf('const me = await getMe().catch(() => null);');

	assert.notEqual(markerRecheckIdx, -1, 'the post-await marker recheck block must exist');
	assert.notEqual(teardownIdx, -1, 'a stale marker must reuse the teardown helper');
	assert.notEqual(returnIdx, -1);
	assert.notEqual(meIdx, -1);

	assert.ok(
		markerRecheckIdx < teardownIdx && teardownIdx < returnIdx && returnIdx < meIdx,
		'a stale marker must tear down and return before the identity check ever runs'
	);
});

test('a cross-tab logout/login during requestAndSubscribe tears down via identity mismatch', () => {
	const fn = extractRecoverIntendedPush();
	const meIdx = fn.indexOf('const me = await getMe().catch(() => null);');
	const mismatchIdx = fn.indexOf('if (!me || me.id !== userId) {', meIdx);
	const teardownIdx = fn.indexOf('await teardownRecoveredSub(sub);', mismatchIdx);
	const returnIdx = fn.indexOf('return;', teardownIdx);
	const signalIdx = fn.indexOf('signalPushRecovered();');

	assert.notEqual(meIdx, -1, 'identity must be re-verified via a server round trip');
	assert.notEqual(mismatchIdx, -1);
	assert.notEqual(teardownIdx, -1, 'an identity mismatch must reuse the teardown helper');
	assert.notEqual(returnIdx, -1);

	assert.ok(
		meIdx < mismatchIdx &&
			mismatchIdx < teardownIdx &&
			teardownIdx < returnIdx &&
			returnIdx < signalIdx,
		'a mismatched (or unreachable) identity must tear down and return before the pulse'
	);

	const mismatchBranch = fn.slice(mismatchIdx, returnIdx + 'return;'.length);
	assert.doesNotMatch(
		mismatchBranch,
		/clearPushIntent/,
		'the marker records the ORIGINAL user intent and must survive an identity mismatch'
	);
});

test('recoverIntendedPush reuses teardownRecoveredSub for both post-await mismatches', () => {
	const fn = extractRecoverIntendedPush();
	const calls = [...fn.matchAll(/await teardownRecoveredSub\(sub\);/g)];
	assert.equal(calls.length, 2, 'the marker and identity mismatches must both reuse the helper');
	for (const call of calls) {
		const after = fn.slice(call.index, call.index + 120);
		assert.match(after, /return;/, 'each teardown call must be followed by a return');
	}
});

test('recoverIntendedPush re-checks permission right before subscribing (no re-prompt)', () => {
	const fn = extractRecoverIntendedPush();
	const emptyKeyIdx = fn.indexOf('if (!public_key) return;');
	const firstIntentRecheckIdx = fn.indexOf('if (getPushIntent() !== userId) return;', emptyKeyIdx);
	const permMatches = [...fn.matchAll(/if \(Notification\.permission !== 'granted'\)/g)];
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key);');

	assert.notEqual(emptyKeyIdx, -1);
	assert.notEqual(firstIntentRecheckIdx, -1);
	assert.notEqual(subIdx, -1);
	assert.equal(
		permMatches.length,
		2,
		'permission must be checked twice: once at entry, once right before subscribing'
	);

	const secondPermIdx = permMatches[1].index;
	assert.ok(
		emptyKeyIdx < firstIntentRecheckIdx &&
			firstIntentRecheckIdx < secondPermIdx &&
			secondPermIdx < subIdx,
		'the second permission check must sit after the key fetch/intent recheck, before subscribe'
	);

	const gap = fn.slice(secondPermIdx, subIdx);
	assert.doesNotMatch(
		gap,
		/await /,
		'nothing may await between the second permission check and requestAndSubscribe'
	);
});

test('recoverIntendedPush never pulses on the denied, empty-key, or failure paths', () => {
	const fn = extractRecoverIntendedPush();
	const permissionBranch = fn.slice(
		fn.indexOf("Notification.permission !== 'granted'"),
		fn.indexOf('try {')
	);
	assert.doesNotMatch(
		permissionBranch,
		/signalPushRecovered/,
		'a denied/default permission must not pulse the signal'
	);

	const emptyKeyIdx = fn.indexOf('if (!public_key) return;');
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key);');
	assert.ok(emptyKeyIdx < subIdx, 'the empty-key return must precede the subscribe attempt');

	const catchBody = fn.slice(fn.indexOf('} catch {'));
	assert.doesNotMatch(
		catchBody,
		/signalPushRecovered/,
		'a swallowed failure must not pulse the signal'
	);

	const pulseCalls = fn.match(/signalPushRecovered\(\)/g) ?? [];
	assert.equal(pulseCalls.length, 1, 'signalPushRecovered must be called from exactly one site');
});

test('settings consumes pushRecoverySignal and flips the toggle only when not busy', () => {
	assert.ok(
		/import \{ pushRecoverySignal \} from '\$lib\/push-recovery-signal';/.test(settingsPage),
		'settings must import the shared signal'
	);
	const effectBody = settingsPage.match(
		/\$effect\(\(\) => \{\s*const signal = \$pushRecoverySignal;[\s\S]*?\n\t\}\);/
	)?.[0];
	assert.ok(effectBody, 'settings must subscribe to the signal inside an $effect');
	assert.ok(
		/if \(signal === lastRecoverySignal\) return;/.test(effectBody),
		'only a genuine increment (not the initial read) must react'
	);
	assert.ok(
		/if \(pushBusy\) return;/.test(effectBody),
		'an in-flight user toggle must not be fought by the background pulse'
	);
	const busyIdx = effectBody.indexOf('if (pushBusy) return;');
	const flipIdx = effectBody.indexOf('pushSubscribed = true;');
	assert.ok(busyIdx !== -1 && flipIdx !== -1 && busyIdx < flipIdx);
});

test('push-intent.ts and service-worker.ts are untouched by the new signal', () => {
	assert.doesNotMatch(
		pushIntent,
		/push-recovery-signal|signalPushRecovered|pushRecoverySignal/,
		'push-intent.ts must stay framework-free and signal-free'
	);
	assert.doesNotMatch(
		serviceWorker,
		/push-recovery-signal|signalPushRecovered|pushRecoverySignal/,
		'the service worker must never touch the recovery signal'
	);
});
