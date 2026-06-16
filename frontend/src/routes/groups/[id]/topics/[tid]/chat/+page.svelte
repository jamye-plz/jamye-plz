<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { getTopic } from '$lib/api/topic.api';
	import ChatRoom from '$lib/components/ChatRoom.svelte';

	const groupId = $derived(page.params.id);
	const topicId = $derived(page.params.tid);

	const topicQuery = createQuery(() => ({
		queryKey: ['topic', topicId],
		queryFn: () => getTopic(groupId, topicId)
	}));

	// Per-topic chatroom: a separate room scoped to this topic, isolated from the
	// group main chat (content is not shared between the two).
	const chatroomId = $derived(topicQuery.data?.chatroom_id ?? '');
</script>

<ChatRoom
	{groupId}
	{chatroomId}
	title={topicQuery.data?.title ?? '주제 채팅'}
	backHref={`/groups/${groupId}/topics/${topicId}`}
/>
