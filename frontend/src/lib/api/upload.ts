/**
 * Direct-to-object-store upload helper, shared by topic media and chat media.
 *
 * Goes straight to the presigned MinIO URL — no `/api` prefix and no
 * credentials, since the signature in the URL is the authorization.
 */

/**
 * PUT a blob to a presigned URL.
 *
 * `contentType` MUST be byte-identical to the value sent to the presign
 * endpoint: the signature binds Content-Type (and Content-Length), so any
 * mismatch makes MinIO reject the upload with a signature error.
 */
export async function uploadToPresignedUrl(
	uploadUrl: string,
	file: Blob,
	contentType: string
): Promise<void> {
	const res = await fetch(uploadUrl, {
		method: 'PUT',
		body: file,
		headers: { 'Content-Type': contentType }
	});
	if (!res.ok) {
		throw new Error(`MinIO upload failed: ${res.status}`);
	}
}
