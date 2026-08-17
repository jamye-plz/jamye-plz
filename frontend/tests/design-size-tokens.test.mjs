import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const frontendRoot = fileURLToPath(new URL('..', import.meta.url));
const sourceRoot = join(frontendRoot, 'src');
const styles = readFileSync(join(sourceRoot, 'app.css'), 'utf8');
const composer = readFileSync(join(sourceRoot, 'lib/components/ChatComposer.svelte'), 'utf8');

function readSvelteSources(directory) {
	return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		const path = join(directory, entry.name);
		if (entry.isDirectory()) return readSvelteSources(path);
		return entry.name.endsWith('.svelte') ? [readFileSync(path, 'utf8')] : [];
	});
}

const svelteSource = readSvelteSources(sourceRoot).join('\n');

test('responsive conversation and composer constraints use semantic design tokens', () => {
	assert.match(styles, /--container-conversation:\s*45rem;/);
	assert.match(styles, /--composer-textarea-max-height:\s*7\.5rem;/);

	assert.doesNotMatch(svelteSource, /max-w-\[720px\]/);
	assert.doesNotMatch(svelteSource, /max-h-\[120px\]/);
	assert.match(svelteSource, /max-w-\(--container-conversation\)/);
	assert.match(composer, /max-h-\(--composer-textarea-max-height\)/);
});

test('composer autosizing delegates its cap to CSS', () => {
	assert.match(composer, /el\.style\.height = `\$\{el\.scrollHeight\}px`;/);
	assert.doesNotMatch(composer, /Math\.min\(el\.scrollHeight,\s*120\)/);
});
