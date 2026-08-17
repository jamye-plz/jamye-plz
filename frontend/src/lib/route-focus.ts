import type { AfterNavigate } from '@sveltejs/kit';

export default function shouldMoveRouteFocus({ from, to, type }: AfterNavigate): boolean {
	if (type === 'enter') return false;

	return !(from && to && from.route.id === to.route.id && from.url.pathname === to.url.pathname);
}
