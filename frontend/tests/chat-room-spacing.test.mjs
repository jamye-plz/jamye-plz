import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(
	new URL('../src/lib/components/ChatRoom.svelte', import.meta.url),
	'utf8'
);
const daisyChatStyles = readFileSync(
	new URL('../node_modules/daisyui/components/chat.css', import.meta.url),
	'utf8'
);

test('chat bubble gaps follow the 4px/12px design-system contract', () => {
	const listSpacing = source.match(/max-w-\(--container-conversation\)\s+space-y-(\d+)/)?.[1];
	const spacingPixels = { 1: 4, 2: 8, 3: 12 }[listSpacing];
	const daisyChatPaddingBlockRem = daisyChatStyles.match(
		/\.chat\{.*?padding-block:(\.\d+)rem/
	)?.[1];
	const groupedMessageOffsetPixels = 8;
	const zeroPaddingChatRows = (
		source.match(/class="chat-(?:end|start) chat py-0 \{!showHeader\(i\)/g) ?? []
	).length;

	assert.ok(spacingPixels, 'the message list must use a supported Tailwind spacing token');
	assert.ok(daisyChatPaddingBlockRem, 'the daisyUI chat block padding must remain measurable');
	assert.equal(
		zeroPaddingChatRows,
		2,
		'both incoming and outgoing chat rows must neutralize daisyUI block padding'
	);
	const daisyChatPaddingBlockPixels =
		zeroPaddingChatRows === 2 ? 0 : Number(daisyChatPaddingBlockRem) * 16;
	assert.equal(
		(source.match(/!showHeader\(i\) \? '-mt-2' : ''/g) ?? []).length,
		2,
		'both incoming and outgoing consecutive messages must share the grouping offset'
	);
	assert.equal(
		spacingPixels + daisyChatPaddingBlockPixels * 2 - groupedMessageOffsetPixels,
		4,
		'consecutive messages from the same sender must have a 4px gap'
	);
	assert.equal(
		spacingPixels + daisyChatPaddingBlockPixels * 2,
		12,
		'new sender or minute groups must have a 12px gap'
	);
});
