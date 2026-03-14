# Zotero Web API v3 — Research Findings

Researched 2026-03-14 using API key for user `amornj`.

---

## 1. User ID vs Username

The API requires a **numeric user ID**, not a username. All user-scoped endpoints use `/users/<userID>/...`.

To discover the numeric user ID from an API key, call:

```
GET https://api.zotero.org/keys/current
Header: Zotero-API-Key: <key>
```

Response (confirmed live):

```json
{
  "key": "BIkDlKKe6aVYG0ncz4YVbEEI",
  "userID": 7734498,
  "username": "amornj",
  "access": {
    "user": { "library": true, "files": true, "notes": true, "write": true },
    "groups": { "all": { "library": true, "write": true } }
  }
}
```

**Implementation note:** On first run, call `/keys/current` once, cache the `userID`, and use it for all subsequent requests.

---

## 2. Collection Lookup / Create Flow

### List collections

```
GET /users/{userID}/collections
Header: Zotero-API-Key: <key>
```

Returns a JSON array. Each entry has `data.key` (8-char alphanumeric) and `data.name`. Pagination via `Link` header; max 100 per page.

Confirmed collections exist for this user (e.g., `AC5G227G` = "pdf-up-test-temp", `8USXTIDU` = "amyloidosis").

### Find by name

No server-side name filter exists. You must fetch all collections and match `data.name` client-side.

### Create a collection

```
POST /users/{userID}/collections
Header: Zotero-API-Key: <key>
Header: Content-Type: application/json

[{ "name": "My Collection" }]
```

Response includes `success` map with the new collection key.

### Recommended flow for pdf-up

1. `GET /users/{userID}/collections` — fetch all, search for target name.
2. If not found, `POST` to create it.
3. Cache the collection key for item creation.

---

## 3. Parent Item Creation (for a PDF document)

### Get the item template

```
GET https://api.zotero.org/items/new?itemType=document
```

Returns (confirmed live):

```json
{
  "itemType": "document",
  "title": "",
  "creators": [{ "creatorType": "author", "firstName": "", "lastName": "" }],
  "abstractNote": "", "type": "", "date": "", "publisher": "", "place": "",
  "DOI": "", "citationKey": "", "url": "", "accessDate": "", "archive": "",
  "archiveLocation": "", "shortTitle": "", "language": "", "libraryCatalog": "",
  "callNumber": "", "rights": "", "extra": "",
  "tags": [], "collections": [], "relations": {}
}
```

### Create the parent item

```
POST /users/{userID}/items
Header: Zotero-API-Key: <key>
Header: Content-Type: application/json

[
  {
    "itemType": "document",
    "title": "My PDF Title",
    "collections": ["AC5G227G"],
    "tags": [{"tag": "pdf-up"}]
  }
]
```

Only `itemType` is strictly required; `tags`, `collections`, and `relations` are optional but useful. All other fields are optional.

Response `200 OK`:

```json
{
  "success": { "0": "<parentItemKey>" },
  "unchanged": {},
  "failed": {}
}
```

---

## 4. PDF Attachment Upload (Binary File Upload)

This is a **two-phase process**: first create the attachment item metadata, then upload the binary file.

### Phase A: Create the attachment item

```
POST /users/{userID}/items
Header: Zotero-API-Key: <key>
Header: Content-Type: application/json

[
  {
    "itemType": "attachment",
    "linkMode": "imported_file",
    "parentItem": "<parentItemKey>",
    "title": "filename.pdf",
    "contentType": "application/pdf",
    "filename": "filename.pdf",
    "tags": []
  }
]
```

Key fields from the template (confirmed live):
- `linkMode`: must be `"imported_file"` for uploaded files
- `parentItem`: key of the parent item created in step 3
- `contentType`: `"application/pdf"`
- `filename`: the PDF filename
- `md5` and `mtime`: set to `null` on creation; populated after file upload

**Parent + child in one request:** If creating both in the same POST array, the parent must come first, and the child must include a locally-generated 8-char key.

### Phase B: Upload the binary file

#### Step 1 — Request upload authorization

```
POST /users/{userID}/items/<attachmentItemKey>/file
Header: Zotero-API-Key: <key>
Header: Content-Type: application/x-www-form-urlencoded
Header: If-None-Match: *

Body: md5=<fileMD5>&filename=<name>&filesize=<bytes>&mtime=<millisTimestamp>
```

`If-None-Match: *` is used for new uploads (no existing file). For updates, use `If-Match: <old-md5>`.

Response (JSON):

```json
{
  "url": "<S3-upload-URL>",
  "contentType": "<required-content-type>",
  "prefix": "<prefix-string>",
  "suffix": "<suffix-string>",
  "uploadKey": "<key>"
}
```

If the file already exists on the server: `{"exists": 1}` — skip to registration.

#### Step 2 — Upload to S3

```
POST <url-from-step-1>
Header: Content-Type: <contentType-from-step-1>

Body: <prefix><raw-file-bytes><suffix>
```

The body is literally the prefix string + file bytes + suffix string concatenated.

#### Step 3 — Register the upload

```
POST /users/{userID}/items/<attachmentItemKey>/file
Header: Zotero-API-Key: <key>
Header: Content-Type: application/x-www-form-urlencoded
Header: If-None-Match: *

Body: upload=<uploadKey>
```

Response: `204 No Content` on success.

---

## 5. Required Scopes / Permissions

From the `/keys/current` response, the current key has **full permissions**:

| Scope | Permission |
|-------|-----------|
| `user.library` | `true` — read/browse library |
| `user.files` | `true` — **required** for file upload |
| `user.notes` | `true` — read/write notes |
| `user.write` | `true` — **required** for creating items/collections |

**Minimal required for pdf-up:**
- `user.library` — read collections, items
- `user.write` — create items and collections
- `user.files` — upload PDF binary

`user.notes` and `groups.*` are not needed unless those features are used.

---

## 6. Caveats

1. **Numeric user ID required.** The API does not accept usernames in URL paths. Always resolve via `/keys/current` first.

2. **No server-side collection name search.** Must fetch all collections and filter client-side. For large libraries, handle pagination (max 100 per response, `Link` header for next page).

3. **File upload is three HTTP requests.** Authorization, S3 upload, then registration. All three must succeed. The S3 upload body format (prefix + bytes + suffix) is unusual — not a standard multipart form.

4. **Rate limiting.** Watch for `Backoff` header (advisory) and `429` responses (hard limit with `Retry-After`). Reduce concurrency if triggered.

5. **`If-None-Match: *` vs `If-Match`.** Use `If-None-Match: *` for first-time file uploads. Use `If-Match: <md5>` when replacing an existing file. Getting this wrong returns `412 Precondition Failed`.

6. **Max 50 items per write request.** The API accepts up to 50 items in a single POST to `/items`.

7. **Item key for same-request parent+child.** If creating parent and child attachment in one POST, you must generate the child's key locally (random 8-char alphanumeric) and place the child after the parent in the array.

8. **`contentType` on attachment item vs upload.** The `contentType` field on the attachment item metadata is separate from the `Content-Type` header returned by the upload authorization step. Both must be set correctly.

9. **Write token or version header.** Write requests should include either `Zotero-Write-Token: <random-32-char>` (for idempotency) or `If-Unmodified-Since-Version: <version>` (for conflict detection). The write token is simpler for one-shot ingestion.

10. **Authentication header format.** Either `Zotero-API-Key: <key>` or `Authorization: Bearer <key>` works. The header approach is preferred over query parameter `?key=` because pagination URLs from `Link` headers can be used directly.
