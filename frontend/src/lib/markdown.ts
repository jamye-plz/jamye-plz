import { marked } from 'marked';
import DOMPurify from 'dompurify';

// User-authored markdown (chat messages, topic bodies) → sanitized HTML.
// Allowed: headings h1–h3, un/ordered lists, GFM task lists, tables, code
// (inline + block), links. Images and raw HTML are stripped. Links are shown
// as full external links and open in a new tab.

marked.setOptions({ gfm: true, breaks: true });

// Tags we render. h4–h6 (and anything else) are dropped to plain text by
// DOMPurify's KEEP_CONTENT; <img> is forbidden outright.
const ALLOWED_TAGS = [
	'h1',
	'h2',
	'h3',
	'p',
	'br',
	'hr',
	'strong',
	'em',
	'del',
	'blockquote',
	'ul',
	'ol',
	'li',
	'input', // GFM task-list checkboxes (rendered disabled)
	'table',
	'thead',
	'tbody',
	'tr',
	'th',
	'td',
	'pre',
	'code',
	'a'
];
const ALLOWED_ATTR = ['href', 'target', 'rel', 'type', 'checked', 'disabled', 'align'];

let hookInstalled = false;
function installHook() {
	if (hookInstalled) return;
	hookInstalled = true;
	// Make every link a safe external link (full URL, new tab).
	DOMPurify.addHook('afterSanitizeAttributes', (node) => {
		if (node.tagName === 'A') {
			node.setAttribute('target', '_blank');
			node.setAttribute('rel', 'noopener noreferrer nofollow');
		}
	});
}

const cache = new Map<string, string>();

export function renderMarkdown(src: string | null | undefined): string {
	if (!src) return '';
	const cached = cache.get(src);
	if (cached !== undefined) return cached;

	installHook();
	const rawHtml = marked.parse(src, { async: false }) as string;
	const clean = DOMPurify.sanitize(rawHtml, {
		ALLOWED_TAGS,
		ALLOWED_ATTR,
		FORBID_TAGS: ['img'],
		FORBID_ATTR: ['src', 'srcset', 'style', 'onerror', 'onload']
	});
	cache.set(src, clean);
	return clean;
}
