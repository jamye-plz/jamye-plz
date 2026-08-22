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
const layoutSvelte = readFileSync(new URL('../src/routes/+layout.svelte', import.meta.url), 'utf8');
const serviceWorker = readFileSync(new URL('../src/service-worker.ts', import.meta.url), 'utf8');
const pushIntent = readFileSync(new URL('../src/lib/push-intent.ts', import.meta.url), 'utf8');
const pushRecoverySignal = readFileSync(
	new URL('../src/lib/push-recovery-signal.ts', import.meta.url),
	'utf8'
);
const swReadySignal = readFileSync(
	new URL('../src/lib/sw-ready-signal.ts', import.meta.url),
	'utf8'
);
const notificationTypes = readFileSync(
	new URL('../src/lib/types/notification.types.ts', import.meta.url),
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

test('recovery captures the logout generation as its first statement', () => {
	const fn = extractRecoverIntendedPush();
	assert.ok(
		fn.startsWith(
			'async function recoverIntendedPush(userId: string): Promise<void> {\n' +
				'\t// Snapshot the logout generation before anything else: if a logout\n' +
				"\t// starts anywhere later in this function's lifetime (detachPushOnLogout\n" +
				'\t// bumps it), this recovery must not complete after that point even\n' +
				'\t// though it began before it.\n' +
				'\tconst startGen = logoutGeneration;'
		),
		'startGen must be captured before any other statement, including the entry gate'
	);
});

test('recovery entry gate rejects a mismatched marker OR an explicit opt-out', () => {
	const fn = extractRecoverIntendedPush();
	const startGenIdx = fn.indexOf('const startGen = logoutGeneration;');
	const entryGateIdx = fn.indexOf(
		'if (getPushIntent() !== userId || hasExplicitPushOptOut(userId)) return;'
	);
	assert.notEqual(startGenIdx, -1);
	assert.notEqual(entryGateIdx, -1);
	assert.ok(
		startGenIdx < entryGateIdx,
		'startGen must be captured before the entry gate can short-circuit'
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
		/await requestAndSubscribe\(public_key, userId\);/.test(fn),
		'subscribe must only be reached once permission is confirmed granted'
	);
});

test('denied/default permission removes the marker and skips the subscribe attempt', () => {
	const fn = extractRecoverIntendedPush();
	const permIdx = fn.indexOf("Notification.permission !== 'granted'");
	const clearIdx = fn.indexOf('clearPushIntent();');
	const subscribeIdx = fn.indexOf('requestAndSubscribe(public_key, userId)');
	assert.notEqual(permIdx, -1);
	assert.notEqual(clearIdx, -1);
	assert.notEqual(subscribeIdx, -1);
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
	const subscribeIdx = fn.indexOf('await requestAndSubscribe(public_key, userId);');
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

test('service-worker.ts never imports push-intent or either reactive signal', () => {
	assert.doesNotMatch(
		serviceWorker,
		/push-intent/,
		'the service worker has no localStorage and must never touch the intent module'
	);
	assert.doesNotMatch(
		serviceWorker,
		/push-recovery-signal|pushRecoverySignal|signalPushRecovered/,
		'the service worker must never touch the recovery signal'
	);
	assert.doesNotMatch(
		serviceWorker,
		/sw-ready-signal|swRegisteredSignal|signalSwRegistered/,
		'the service worker must never touch the SW-ready signal'
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

test('settings toggle OFF success records an explicit opt-out, not just a clear', () => {
	const fn = extractOnTogglePush();
	const elseIdx = fn.indexOf('} else {');
	const offIdx = fn.indexOf('if (uid) setPushIntentOff(uid);');
	assert.notEqual(elseIdx, -1);
	assert.notEqual(offIdx, -1);
	assert.ok(elseIdx < offIdx, 'setPushIntentOff must run in the turnOff branch');
	assert.doesNotMatch(
		fn,
		/clearPushIntent/,
		'toggle-OFF must use the durable opt-out key, not the ambiguous clear'
	);
});

test('a failed toggle never reaches the marker calls (both sit before the catch)', () => {
	const fn = extractOnTogglePush();
	const catchIdx = fn.indexOf('} catch (err) {');
	const setIdx = fn.indexOf('if (uid) setPushIntent(uid);');
	const offIdx = fn.indexOf('if (uid) setPushIntentOff(uid);');
	assert.notEqual(catchIdx, -1);
	assert.ok(setIdx < catchIdx, 'setPushIntent must run before the catch, i.e. only on success');
	assert.ok(offIdx < catchIdx, 'setPushIntentOff must run before the catch, i.e. only on success');
});

test('settings onMount backfill is guarded by hasExplicitPushOptOut', () => {
	assert.ok(
		settingsPage.includes(
			'const uid = meQuery.data?.id;\n' +
				'\t\t\t\t\t\tif (uid && !hasExplicitPushOptOut(uid)) setPushIntent(uid);'
		),
		'backfill must skip an explicit opt-out regardless of concurrent-tab write ordering'
	);
});

test('push-intent is imported by push.api.ts and settings, never by the service worker', () => {
	const pushApiImport =
		"import { clearPushIntent, getPushIntent, hasExplicitPushOptOut } from '$lib/push-intent';";
	assert.ok(
		pushApi.includes(pushApiImport),
		'push.api.ts must import the intent accessors it uses, including the opt-out reader'
	);
	const settingsImport =
		"import { hasExplicitPushOptOut, setPushIntent, setPushIntentOff } from '$lib/push-intent';";
	assert.ok(
		settingsPage.includes(settingsImport),
		'settings must import the opt-out-aware intent writers it uses'
	);
	assert.doesNotMatch(serviceWorker, /from '\$lib\/push-intent'/);
});

// --- explicit opt-out: separate key, read-precedence in both recovery gates ---

test('the pre-subscribe recheck stays intent-only (unaffected by the opt-out fix)', () => {
	const fn = extractRecoverIntendedPush();
	const emptyKeyIdx = fn.indexOf('if (!public_key) return;');
	const recheckMatches = [...fn.matchAll(/if \(getPushIntent\(\) !== userId\) return;/g)];
	assert.notEqual(emptyKeyIdx, -1);
	assert.equal(
		recheckMatches.length,
		1,
		'exactly one plain (non-compound) intent-only recheck must remain: the pre-subscribe one'
	);
	assert.ok(
		emptyKeyIdx < recheckMatches[0].index,
		'the pre-subscribe recheck must sit after the public_key check'
	);
});

test('the final post-await recheck also gates on opt-out AND the logout generation', () => {
	const fn = extractRecoverIntendedPush();
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key, userId);');
	const notSubIdx = fn.indexOf('if (!sub) return;', subIdx);
	const recheckIdx = fn.indexOf('if (\n\t\t\tgetPushIntent() !== userId ||', notSubIdx);
	const optOutIdx = fn.indexOf('hasExplicitPushOptOut(userId) ||', recheckIdx);
	const genIdx = fn.indexOf('startGen !== logoutGeneration', optOutIdx);
	const teardownIdx = fn.indexOf('await teardownRecoveredSub(sub, userId, startGen);', genIdx);
	const signalIdx = fn.indexOf('signalPushRecovered();');

	assert.notEqual(subIdx, -1);
	assert.notEqual(notSubIdx, -1);
	assert.notEqual(recheckIdx, -1, 'the final recheck must start with the same condition as entry');
	assert.notEqual(optOutIdx, -1, 'the opt-out term must be part of the final recheck');
	assert.notEqual(genIdx, -1, 'the logout-generation term must be part of the final recheck');
	assert.notEqual(teardownIdx, -1, 'teardown must be called with the captured startGen');
	assert.notEqual(signalIdx, -1);
	assert.ok(
		subIdx < notSubIdx &&
			notSubIdx < recheckIdx &&
			recheckIdx < optOutIdx &&
			optOutIdx < genIdx &&
			genIdx < teardownIdx &&
			teardownIdx < signalIdx,
		'subscribe -> !sub bail -> compound (marker/opt-out/generation) recheck+teardown -> pulse'
	);
});

test('teardownRecoveredSub restores intent only when not opted out AND same generation', () => {
	const fn = extractTeardownRecoveredSub();
	const condIdx = fn.indexOf('if (\n\t\tgetPushIntent() === userId &&');
	const optOutIdx = fn.indexOf('!hasExplicitPushOptOut(userId) &&', condIdx);
	const genIdx = fn.indexOf('startGen === logoutGeneration', optOutIdx);
	assert.notEqual(condIdx, -1, 'the restored-intent branch must exist');
	assert.notEqual(optOutIdx, -1, 'restore must require the absence of an opt-out');
	assert.notEqual(genIdx, -1, 'restore must require the SAME logout generation as when started');
	assert.ok(condIdx < optOutIdx && optOutIdx < genIdx, 'all three terms must gate the same branch');
});

test('hasExplicitPushOptOut is imported by push.api.ts and used at all three gates', () => {
	assert.ok(
		/import \{ clearPushIntent, getPushIntent, hasExplicitPushOptOut \}/.test(pushApi),
		'hasExplicitPushOptOut must be imported alongside the other intent accessors'
	);
	const calls = pushApi.match(/hasExplicitPushOptOut\(userId\)/g) ?? [];
	assert.equal(
		calls.length,
		3,
		'entry gate, final recheck, and teardown restore must all consult the opt-out key'
	);
});

test('logoutGeneration is a module-local counter bumped first by detachPushOnLogout', () => {
	assert.ok(
		/^let logoutGeneration = 0;$/m.test(pushApi),
		'logoutGeneration must be a plain module-level mutable counter'
	);
	const detachFn = pushApi.match(
		/export async function detachPushOnLogout\(\): Promise<void> \{[\s\S]*?\n}\n/
	)?.[0];
	assert.ok(detachFn, 'detachPushOnLogout must exist');
	assert.ok(
		detachFn.startsWith(
			'export async function detachPushOnLogout(): Promise<void> {\n' +
				'\t// First statement, unconditional: any in-flight recovery must see this\n' +
				'\t// logout regardless of which branch below runs (or whether it hangs).\n' +
				'\tlogoutGeneration++;'
		),
		'logoutGeneration must be incremented as the unconditional first statement'
	);
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

// --- Server-side binding (expected_user_id) supersedes client-side getMe() ---

test('PushSubscriptionPayload declares an optional expected_user_id field', () => {
	assert.ok(
		/expected_user_id\?: string;/.test(notificationTypes),
		'the payload type must declare the optional server-side binding field'
	);
});

test('requestAndSubscribe accepts an optional expectedUserId and forwards it', () => {
	assert.ok(
		pushApi.includes(
			'export async function requestAndSubscribe(\n' +
				'\tvapidPublicKey: string,\n' +
				'\texpectedUserId?: string\n' +
				'): Promise<PushSubscription | null> {'
		),
		'requestAndSubscribe must accept an optional expectedUserId parameter'
	);
	assert.ok(
		/expected_user_id: expectedUserId/.test(pushApi),
		'the subscribePush payload must forward expectedUserId as expected_user_id'
	);
});

test('recoverIntendedPush passes userId as expectedUserId into requestAndSubscribe', () => {
	const fn = extractRecoverIntendedPush();
	assert.ok(
		/const sub = await requestAndSubscribe\(public_key, userId\);/.test(fn),
		'recovery must bind the subscribe POST to the intended user server-side'
	);
});

test('settings toggle path calls requestAndSubscribe without an expectedUserId', () => {
	const fn = extractOnTogglePush();
	assert.ok(
		/await requestAndSubscribe\(vapidPublicKey!\);/.test(fn),
		'the explicit settings toggle needs no server-side binding (it is already a user gesture)'
	);
});

test('push.api.ts no longer imports getMe (server binding supersedes identity check)', () => {
	assert.doesNotMatch(
		pushApi,
		/from '\.\/auth\.api'/,
		'the getMe-based identity re-check was replaced by expected_user_id server binding'
	);
});

// --- teardownRecoveredSub: restored-intent re-POST ---

test('teardownRecoveredSub takes sub, userId, and the captured startGen', () => {
	const fn = extractTeardownRecoveredSub();
	assert.ok(
		fn.startsWith(
			'async function teardownRecoveredSub(\n' +
				'\tsub: PushSubscription,\n' +
				'\tuserId: string,\n' +
				'\tstartGen: number\n' +
				'): Promise<void> {'
		),
		'teardownRecoveredSub must accept the userId and the logout generation to re-check'
	);
});

test('teardownRecoveredSub races a delete against a timeout before any local decision', () => {
	const fn = extractTeardownRecoveredSub();
	const raceIdx = fn.indexOf('await Promise.race([');
	const serverDeleteIdx = fn.indexOf('unsubscribePush(sub.endpoint).catch(() => {})');
	const timeoutIdx = fn.indexOf('setTimeout(resolve, 3000)');
	assert.notEqual(raceIdx, -1);
	assert.notEqual(serverDeleteIdx, -1);
	assert.notEqual(timeoutIdx, -1);
	assert.ok(
		raceIdx < serverDeleteIdx && serverDeleteIdx < timeoutIdx,
		'must race the server delete against a timeout before any local decision'
	);
});

test('teardownRecoveredSub re-reads the live subscription before restoring', () => {
	const fn = extractTeardownRecoveredSub();
	const raceCloseIdx = fn.indexOf(']);');
	const condIdx = fn.indexOf('if (\n\t\tgetPushIntent() === userId &&', raceCloseIdx);
	const regIdx = fn.indexOf('const reg = await getActiveRegistration();', condIdx);
	const currentIdx = fn.indexOf(
		'const current = reg ? await reg.pushManager.getSubscription() : null;',
		regIdx
	);
	const endpointCheckIdx = fn.indexOf(
		'if (current && current.endpoint === sub.endpoint) {',
		currentIdx
	);

	assert.notEqual(raceCloseIdx, -1);
	assert.notEqual(condIdx, -1, 'the restored-intent branch must exist');
	assert.notEqual(regIdx, -1, 'restore must re-fetch the active registration');
	assert.notEqual(currentIdx, -1, 'restore must re-read the LIVE subscription, not trust `sub`');
	assert.notEqual(endpointCheckIdx, -1, 'restore must only proceed on a matching live endpoint');
	assert.ok(
		raceCloseIdx < condIdx &&
			condIdx < regIdx &&
			regIdx < currentIdx &&
			currentIdx < endpointCheckIdx,
		'the live re-read must happen inside the restored-intent branch, before any re-POST'
	);
});

test('teardownRecoveredSub re-POSTs using the CURRENT subscription, only on endpoint match', () => {
	const fn = extractTeardownRecoveredSub();
	const endpointCheckIdx = fn.indexOf('if (current && current.endpoint === sub.endpoint) {');
	const rawIdx = fn.indexOf('const raw = current.toJSON();', endpointCheckIdx);
	const rePostIdx = fn.indexOf('await subscribePush({', rawIdx);
	const endpointFieldIdx = fn.indexOf('endpoint: current.endpoint,', rePostIdx);
	const expectedUserIdIdx = fn.indexOf('expected_user_id: userId', endpointFieldIdx);
	const catchIdx = fn.indexOf('}).catch(() => {});', expectedUserIdIdx);
	const closingIfIdx = fn.indexOf('\n\t\t}\n\t\treturn;', catchIdx);
	const unsubscribeIdx = fn.indexOf('await sub.unsubscribe().catch(() => {});');

	assert.notEqual(endpointCheckIdx, -1);
	assert.notEqual(rawIdx, -1, 're-POST must read coords off the CURRENT subscription, not `sub`');
	assert.notEqual(rePostIdx, -1);
	assert.notEqual(endpointFieldIdx, -1, 're-POST must send the CURRENT endpoint');
	assert.notEqual(expectedUserIdIdx, -1, 're-POST must stay bound to the intended user');
	assert.notEqual(catchIdx, -1, 're-POST must be best-effort (swallowed failure)');
	assert.notEqual(closingIfIdx, -1, 'the if-block must close, then return either way');
	assert.notEqual(unsubscribeIdx, -1);

	assert.ok(
		endpointCheckIdx < rawIdx &&
			rawIdx < rePostIdx &&
			rePostIdx < endpointFieldIdx &&
			endpointFieldIdx < expectedUserIdIdx &&
			expectedUserIdIdx < catchIdx &&
			catchIdx < closingIfIdx &&
			closingIfIdx < unsubscribeIdx,
		're-POST (bound to the current endpoint) must run, then return, before the fallback unsubscribe'
	);

	const restoredBranch = fn.slice(
		endpointCheckIdx,
		closingIfIdx + '\n\t\t}\n\t\treturn;'.length
	);
	assert.doesNotMatch(
		restoredBranch,
		/signalPushRecovered/,
		'restoring the fresh toggle-ON subscription is not a recovery — no pulse here'
	);
});

test('a null or mismatched current subscription re-POSTs nothing (return is unconditional)', () => {
	const fn = extractTeardownRecoveredSub();
	// The `return;` after the endpoint-match if-block sits OUTSIDE that
	// block, at the same indent as the `if`, so it always runs whether or
	// not the match (and re-POST) happened — a null/different-endpoint
	// `current` simply skips straight to this unconditional return, doing
	// nothing (no re-POST, and no fallback unsubscribe of the dead `sub`
	// either, since that only runs when the OUTER condition fails entirely).
	assert.ok(
		fn.includes(
			'\t\tif (current && current.endpoint === sub.endpoint) {\n' +
				'\t\t\tconst raw = current.toJSON();'
		) && fn.includes('\t\t}\n\t\treturn;\n\t}\n'),
		'the endpoint-match if must be followed by an unconditional return outside its own braces'
	);
});

// --- post-subscribe marker recheck + pulse ---

test('recoverIntendedPush signals only after subscribe succeeds and the recheck passes', () => {
	const fn = extractRecoverIntendedPush();
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key, userId);');
	const notSubIdx = fn.indexOf('if (!sub) return;');
	const recheckIdx = fn.indexOf('if (\n\t\t\tgetPushIntent() !== userId ||', notSubIdx);
	const signalIdx = fn.indexOf('signalPushRecovered();');

	assert.notEqual(subIdx, -1, 'the subscribe result must be captured');
	assert.notEqual(notSubIdx, -1, 'a null subscription must bail before signaling');
	assert.notEqual(recheckIdx, -1, 'the post-await compound marker recheck must exist');
	assert.notEqual(signalIdx, -1, 'signalPushRecovered must exist');
	assert.ok(
		subIdx < notSubIdx && notSubIdx < recheckIdx && recheckIdx < signalIdx,
		'the pulse must fire only after subscribe succeeds and the recheck is reconfirmed'
	);
});

test('a toggle-OFF, opt-out, or logout mid-requestAndSubscribe tears the sub back down', () => {
	const fn = extractRecoverIntendedPush();
	const notSubIdx = fn.indexOf('if (!sub) return;');
	const recheckIdx = fn.indexOf('if (\n\t\t\tgetPushIntent() !== userId ||', notSubIdx);
	const teardownIdx = fn.indexOf('await teardownRecoveredSub(sub, userId, startGen);', recheckIdx);
	const returnIdx = fn.indexOf('return;', teardownIdx);
	const signalIdx = fn.indexOf('signalPushRecovered();');

	assert.notEqual(recheckIdx, -1, 'the post-await compound marker recheck block must exist');
	assert.notEqual(teardownIdx, -1, 'a stale marker, opt-out, or logout must reuse the teardown');
	assert.notEqual(returnIdx, -1);
	assert.notEqual(signalIdx, -1);
	assert.ok(
		recheckIdx < teardownIdx && teardownIdx < returnIdx && returnIdx < signalIdx,
		'a stale marker, opt-out, or logout must tear down and return before ever reaching the pulse'
	);
});

test('the marker recheck runs synchronously right before the pulse, no intervening await', () => {
	const fn = extractRecoverIntendedPush();
	const notSubIdx = fn.indexOf('if (!sub) return;');
	const recheckIdx = fn.indexOf('if (\n\t\t\tgetPushIntent() !== userId ||', notSubIdx);
	const signalIdx = fn.indexOf('signalPushRecovered();');

	assert.notEqual(recheckIdx, -1);
	assert.notEqual(signalIdx, -1);

	const between = fn.slice(recheckIdx, signalIdx + 'signalPushRecovered();'.length);
	const expected =
		'if (\n' +
		'\t\t\tgetPushIntent() !== userId ||\n' +
		'\t\t\thasExplicitPushOptOut(userId) ||\n' +
		'\t\t\tstartGen !== logoutGeneration\n' +
		'\t\t) {\n' +
		'\t\t\tawait teardownRecoveredSub(sub, userId, startGen);\n' +
		'\t\t\treturn;\n' +
		'\t\t}\n' +
		'\t\tsignalPushRecovered();';
	assert.equal(
		between,
		expected,
		'nothing (in particular no await) may sit between the recheck and the pulse'
	);
});

test('recoverIntendedPush re-checks permission right before subscribing (no re-prompt)', () => {
	const fn = extractRecoverIntendedPush();
	const emptyKeyIdx = fn.indexOf('if (!public_key) return;');
	const firstIntentRecheckIdx = fn.indexOf('if (getPushIntent() !== userId) return;', emptyKeyIdx);
	const permMatches = [...fn.matchAll(/if \(Notification\.permission !== 'granted'\)/g)];
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key, userId);');

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
	const subIdx = fn.indexOf('const sub = await requestAndSubscribe(public_key, userId);');
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

test('push-intent.ts is untouched by either reactive signal', () => {
	assert.doesNotMatch(
		pushIntent,
		/push-recovery-signal|signalPushRecovered|pushRecoverySignal/,
		'push-intent.ts must stay framework-free and recovery-signal-free'
	);
	assert.doesNotMatch(
		pushIntent,
		/sw-ready-signal|swRegisteredSignal|signalSwRegistered/,
		'push-intent.ts must stay framework-free and SW-signal-free'
	);
});

// --- Fix B: retry reclaim when a SW registration appears mid-session ---

test('sw-ready-signal.ts exports a writable pulse and a publisher', () => {
	assert.ok(
		/export const swRegisteredSignal = writable\(0\);/.test(swReadySignal),
		'the signal must be a plain writable store'
	);
	assert.ok(
		/export function signalSwRegistered\(\): void/.test(swReadySignal),
		'signalSwRegistered must be the publish entry point'
	);
});

test('+layout.svelte registers the SW with immediate:true and onRegisteredSW', () => {
	assert.ok(
		/import \{ signalSwRegistered \} from '\$lib\/sw-ready-signal';/.test(layoutSvelte),
		'the layout must import the SW-ready signal publisher'
	);
	const registerCallIdx = layoutSvelte.indexOf('registerSW({');
	const immediateIdx = layoutSvelte.indexOf('immediate: true,', registerCallIdx);
	const onRegisteredIdx = layoutSvelte.indexOf(
		'onRegisteredSW: () => signalSwRegistered()',
		registerCallIdx
	);
	assert.notEqual(registerCallIdx, -1, 'registerSW must still be called');
	assert.notEqual(immediateIdx, -1, 'immediate: true must be kept unchanged');
	assert.notEqual(onRegisteredIdx, -1, 'onRegisteredSW must publish the SW-ready pulse');
	assert.ok(
		registerCallIdx < immediateIdx && immediateIdx < onRegisteredIdx,
		'immediate and onRegisteredSW must both be part of the same registerSW call'
	);
});

test('the dynamic PWA-register import gating is unchanged', () => {
	assert.ok(
		/if \(import\.meta\.env\.PROD \|\| import\.meta\.env\.VITE_DEV_SW === 'true'\)/.test(
			layoutSvelte
		),
		'the prod/VITE_DEV_SW gate around registering the SW must remain'
	);
	assert.ok(
		/import\('virtual:pwa-register'\)\.then\(\(\{ registerSW \}\) =>/.test(layoutSvelte),
		'the dynamic import of virtual:pwa-register must remain'
	);
});

test('PushReconciler subscribes to swRegisteredSignal and re-runs reclaim on a pulse', () => {
	assert.ok(
		/import \{ swRegisteredSignal \} from '\$lib\/sw-ready-signal';/.test(pushReconciler),
		'PushReconciler must import the SW-ready signal'
	);
	assert.ok(
		/const swPulse = \$swRegisteredSignal;/.test(pushReconciler),
		'the effect must read the SW-ready signal (so it re-runs when the pulse changes)'
	);
	// The re-run key must be a composite of uid AND the pulse, not uid alone,
	// otherwise a pulse arriving for an already-reclaimed uid would not
	// re-trigger reclaim (Svelte effects only re-run when a value THEY READ
	// changes; merely mutating a shared variable from elsewhere would not).
	assert.ok(
		/const key = `\$\{uid\}:\$\{swPulse\}`;/.test(pushReconciler),
		'the dedupe key must combine uid and the SW-ready pulse count'
	);
	assert.ok(
		/if \(key !== lastReclaimedFor\) \{/.test(pushReconciler),
		'reclaim must re-run whenever the composite key changes'
	);
	assert.ok(
		/reclaimPushForCurrentUser\(uid\);/.test(pushReconciler),
		'PushReconciler must still call reclaimPushForCurrentUser(uid)'
	);
});

test('PushReconciler no longer uses a plain uid-only lastReclaimed guard', () => {
	assert.doesNotMatch(
		pushReconciler,
		/uid !== lastReclaimed\b(?!For)/,
		'the old uid-only guard must be replaced by the composite-key guard'
	);
});
