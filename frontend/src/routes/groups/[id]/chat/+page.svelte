<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { getGroup } from '$lib/api/group.api';
	import ChatRoom from '$lib/components/ChatRoom.svelte';

	const groupId = $derived(page.params.id!);

	const groupQuery = createQuery(() => ({
		queryKey: ['group', groupId],
		queryFn: () => getGroup(groupId)
	}));

	// Group main chatroom: normal chat + system reminders (e.g. new topic).
	const chatroomId = $derived(groupQuery.data?.main_chatroom_id ?? '');
</script>

<ChatRoom
	{groupId}
	{chatroomId}
	title={groupQuery.data?.name ?? '그룹 채팅'}
	backHref={`/groups/${groupId}`}
/>
