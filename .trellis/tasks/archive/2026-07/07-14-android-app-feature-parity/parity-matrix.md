# Android feature parity matrix

| Requirement | Android destination / action | Existing contract | Verification |
| --- | --- | --- | --- |
| R1 | Native login/register, PlayCaptcha WebView, launch restore, logout | `/api/auth/playcaptcha`, `/register`, `/login`, `/me`, `/refresh`, `/logout` | Build/lint pass; device checklist: captcha/login/refresh/relaunch/logout |
| R2 | Permission-derived destinations and actions | permissions returned by `/api/auth/me` | `OrbitJsonTest.permissionsComeFromServerPayload`; device user/admin matrix |
| R3 | Dashboard summary, featured excerpt, quick actions | five collection GET endpoints | Compose/device smoke check |
| R4 | Bookmark list/create/delete/favorite/filter/search/move; folder create/reorder/delete | `/api/bookmarks`, `/api/folders` CRUD/PATCH | Unit: sort/filter; device CRUD and non-empty folder error |
| R5 | Excerpt list/create/delete/shuffle | `/api/excerpts` CRUD | Device CRUD and ordering |
| R6 | Plan create/delete/date/count/statistics | `/api/plans` CRUD/PATCH | 7 `PlanMathTest` cases; device count round-trip |
| R7 | Todo list/create/toggle/delete/clear completed | `/api/todos` CRUD/PATCH | Device CRUD and clear completed |
| R8 | Netdisk query/source filters/external open | `GET /api/netdisk/search?kw=` | `OrbitJsonTest.netdiskDecoderKeepsNormalizedMetadata`; device query/filter/link |
| R9 | Conversation CRUD, POST/SSE, stop, interruption, background polling | `/api/hermes-chat/conversations/**` | 5 SSE/projection cases; device stream/stop/background/resume |
| R10 | Users/roles/permissions, role assignment, ban/delete, chat audit | `/api/admin/**` | Device admin matrix and confirmations |
| R11 | Hermes status/start/stop and authenticated Dashboard WebView | `/api/agents/hermes/**`, `/hermes-dashboard/**` | Device HTTP/WebSocket/dashboard check |
| R12 | API 26+, default server/admin override, Debug APK, web regression | Android build plus existing backend | 15 JVM tests, lint, signed APK, `npm test`; device install pending |

## Approved Android-specific adaptations

- Desktop layout becomes Compose navigation and vertically scrolling phone screens; workflows and data remain equivalent.
- Folder order supports explicit move-up/move-down controls in addition to any drag gesture so TalkBack users can reorder.
- PlayCaptcha and Hermes Dashboard remain WebView surfaces; every other product destination is native Compose.
- Global search retains the browser's actual bookmark-only filtering behavior.
- Release signing, offline mutation, notifications, data isolation changes, and new edit workflows are not part of this task.
