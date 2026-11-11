# Application checks

Run a local preview with Python 3.12 or newer:

```powershell
python -B tools/preview.py
```

Open http://127.0.0.1:8081. Preview data lives in `tmp/preview-data`, separate from the Docker volume. This preview uses Python to serve static files and the API on one origin; Nginx and Docker still need separate integration verification.

If port 8081 is unavailable, run `python -B tools/preview.py --port 0` to select a free local port, then open the URL printed by the server.

Run the regression tests (Python standard library and Node.js 18 or newer):

```powershell
python -B -m unittest discover -s tests -v
node --test tests/frontend.test.cjs tests/github_frontend.test.cjs
```

## API and persistence

- `GET /members` returns an array of members, including a server-managed `_version`.
- `POST /members` creates a member. Required fields are text `name`, `nim`, `role`, and a nonempty `skills` array of text. NIM uses ASCII digits and must be unique.
- `PUT /members?index=X` and `DELETE /members?index=X` remain available for the exam contract. Both also accept `?nim=X` for stable member identity.
- The frontend sends `If-Match: "<displayed _version>"` when editing or deleting. Under the storage lock, the backend rejects a stale version with HTTP 409. Direct clients should send this header too; omitted headers retain the original unconditional index-based API behavior.
- PUT replaces the entire member and cannot change NIM. A successful update generates a new version. On a conflict, reload the page and reapply changes to the latest profile.
- `POST /uploads` accepts JPEG, PNG, or WebP bytes up to 5 MiB, checking the file signature. It does not fully decode images. `DELETE /uploads/<filename>` removes an unreferenced upload; referenced photos return 409. The frontend attempts cleanup when an upload succeeds but saving the activity fails.
- Only a missing JSON file means an empty database. Invalid JSON, invalid records, read failures, and write failures return HTTP 503. Existing data is never replaced by an empty fallback. Back up and repair an invalid file before retrying.
- Writes use a temporary file, flush it to disk, then replace the original. Photos are removed only after a successful member write and only when no member references them.
- Legacy valid records receive a calculated version on GET without rewriting the file. Their next successful update stores a new version.

## Profile actions and GitHub projects

Each member row has explicit **Lihat profil** and **Edit profil** links. The edit link opens the profile with its edit dialog already visible. Users add manual projects/activities through **Tambah kegiatan** on that profile.

Members with a GitHub username also show up to three repositories directly in the roster showcase, ordered by latest push. These are clickable repository names. Showcase requests are shared and cached for five minutes in the page so a roster refresh does not repeatedly fetch the same account. Failures have a retry button and do not prevent the member profile from appearing.

The Project tab also displays public GitHub repositories from the saved username. The backend calls `GET https://api.github.com/users/{username}/repos` with `type=owner`, sorted by latest push, in pages of 12. No GitHub token is needed for public repositories. Forks and archived repositories remain visible with labels; listing a repo does not imply sole authorship.

`GET /github/repos?username=NAME&page=1` returns `repositories`, `page`, and `has_next`. Successful responses are cached in memory for five minutes, with at most 128 username/page entries. A server restart clears the cache. GitHub data is displayed live and is not copied into `team_members.json` or the manual activities list. Changes to the GitHub username reset the displayed repositories.

The backend needs outbound HTTPS access to `api.github.com`. GitHub errors, missing users, rate limits, empty results, and network failures have explicit UI states with retry. Existing loaded repositories stay visible if loading the next page fails. Network failures and error responses are not cached.

Reference: [GitHub REST API: list repositories for a user](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user).

## Browser verification still required

Automated coverage includes API behavior, stale and simultaneous edits, index shifts, storage corruption/write failures, server recreation, shared photo cleanup, frontend request headers, errors, timeouts, and dialog interaction logic. The frontend tests use request and dialog mocks; they do not establish browser rendering or full interaction correctness.

Before considering the frontend finished, check these flows in desktop and narrow mobile viewports:

1. Open the welcome page, follow the member link, and verify the empty state.
2. Add a member, reject invalid/duplicate NIMs, and open the profile.
3. Edit profile fields, including clearing optional values.
4. Add activities in all three categories, upload a photo, open it, and delete the activity.
5. Switch activity tabs with mouse and Arrow/Home/End keys; close idle dialogs with Escape and backdrop clicks.
6. Open the same profile in two tabs. Save in one tab, then attempt a stale edit and delete in the other. Both must show a conflict and preserve the first tab's data.
7. Delete a different member while another profile is open; edits/deletes must still target the correct NIM.
8. Stop/restart the preview server. Verify the connection error, automatic roster recovery, and persisted profiles/photos.
9. Check long unbroken names, skills, and email addresses for overflow; verify keyboard focus and reduced-motion settings.
10. Use **Edit profil** directly from the roster; the edit dialog should open without clicking the member name.
11. Save a valid GitHub username and verify public repositories on the Project tab. Load the next page, switch categories, change/clear the username, and test a nonexistent account. Confirm manual activities remain unchanged.

Browser automation was unavailable during this pass, so this checklist is pending. Direct outbound GitHub requests were also blocked by the environment's socket permissions; GitHub integration tests use simulated upstream responses. Docker persistence and Nginx routing are pending the DevOps pass.
