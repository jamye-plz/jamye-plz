import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const topicApi = readFileSync(new URL('../src/lib/api/topic.api.ts', import.meta.url), 'utf8');
const chatRoom = readFileSync(
	new URL('../src/lib/components/ChatRoom.svelte', import.meta.url),
	'utf8'
);
const chatPage = readFileSync(
	new URL('../src/routes/groups/[id]/topics/[tid]/chat/+page.svelte', import.meta.url),
	'utf8'
);

test('renameTopic is exported from topic.api.ts', () => {
	assert.ok(/export function renameTopic/.test(topicApi), 'renameTopic must be exported');
});

test('renameTopic sends only the title field via PATCH', () => {
	assert.ok(
		/renameTopic.*apiPatch.*\{ title \}/s.test(topicApi),
		'renameTopic must call apiPatch with { title }'
	);
});

test('ChatRoom accepts canRenameTitle and onRenameTitle props', () => {
	assert.ok(
		/canRenameTitle\??: boolean/.test(chatRoom),
		'ChatRoom must declare canRenameTitle prop'
	);
	assert.ok(
		/onRenameTitle\??: \(\) => void/.test(chatRoom),
		'ChatRoom must declare onRenameTitle prop'
	);
});

test('ChatRoom renders the 44px pencil trigger only when canRenameTitle is true', () => {
	assert.ok(
		/\{#if canRenameTitle\}/.test(chatRoom),
		'pencil trigger must be guarded by {#if canRenameTitle}'
	);
	assert.ok(
		/btn btn-square size-11 min-h-11 shrink-0 btn-ghost/.test(chatRoom),
		'pencil trigger must use the contract button classes'
	);
	assert.ok(
		/aria-label="주제 이름 수정"/.test(chatRoom),
		'pencil trigger must have Korean aria-label'
	);
});

test('ChatRoom imports the Pencil icon', () => {
	assert.ok(/from '@lucide\/svelte\/icons\/pencil'/.test(chatRoom), 'Pencil icon must be imported');
});

test('chat page wires canRenameTitle and onRenameTitle to ChatRoom', () => {
	assert.ok(
		/canRenameTitle=\{isAuthor\}/.test(chatPage),
		'canRenameTitle must be bound to isAuthor'
	);
	assert.ok(
		/onRenameTitle=\{openTitleEditor\}/.test(chatPage),
		'onRenameTitle must be bound to openTitleEditor'
	);
});

test('rename dialog uses daisyUI modal classes', () => {
	assert.ok(
		/class="modal modal-bottom sm:modal-middle"/.test(chatPage),
		'rename dialog must use daisyUI modal classes (at least one occurrence)'
	);
	assert.ok(/class="modal-box space-y-4"/.test(chatPage), 'rename dialog must have modal-box');
	assert.ok(/class="modal-action gap-2"/.test(chatPage), 'rename dialog must have modal-action');
});

test('rename dialog input has maxlength 256 and Korean label', () => {
	assert.ok(
		/id="topic-title-editor"/.test(chatPage),
		'title input must have id topic-title-editor'
	);
	assert.ok(/maxlength=\{256\}/.test(chatPage), 'title input must enforce maxlength 256');
	assert.ok(/주제 이름/.test(chatPage), 'dialog must have Korean label for the title field');
});

test('submit button is disabled for blank or unchanged input', () => {
	assert.ok(
		/!draftTitle\.trim\(\)/.test(chatPage),
		'submit must be disabled when draft is blank after trim'
	);
	assert.ok(
		/draftTitle\.trim\(\) === topicQuery\.data\?\.title/.test(chatPage),
		'submit must be disabled when draft equals the current title'
	);
});

test('success handler updates topic cache and invalidates topic list', () => {
	assert.ok(
		/setQueryData\(\['topic', topicId\]/.test(chatPage),
		'success must call setQueryData for the single topic'
	);
	assert.ok(
		/invalidateQueries\(\{ queryKey: \['topics', groupId\]/.test(chatPage),
		'success must invalidate the group topic-list cache'
	);
});
