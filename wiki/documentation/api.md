# API Surface

**Stack summary**  
- FastAPI app in `src/main.py` includes routers for auth, chat, holdings, home, Kite Connect, WhatsApp plus a `/healthz` probe.  
- Auth is cookie-based JWT via `src.core.middleware.require_auth`. A valid token is required unless the doc below marks the route as **Public**.  
- Schemas live under `src/api/schemas/*`.

## Authentication (`/auth`)
- `POST /register` — create a user (`UserCreate`) and immediately sets the auth cookie; returns `UserResponse`.  
- `POST /login` — authenticate with `UserLogin`, issues JWT via cookie, returns `UserResponse`.  
- `POST /logout` — clears auth cookie; no body, returns `{message}`.  
- `GET /me` — requires auth; echoes the decoded user profile (`UserResponse`).

## Home Feed (`/api/home`)
- `GET /home` — requires auth; combines WhatsApp integration state and broker catalog. Response is `HomeFeedSchema` with `chat_integrations` (optional WhatsApp payload) and `available_brokers`.

## Holdings (`/holdings`)
- `POST /` — requires auth; accepts `HoldingsRequestSchema` to upsert a single equity position and returns `HoldingsResponseSchema`.  
- `POST /file-upload` — requires auth; multipart form with `broker_id` and Excel/CSV upload. Parses file via broker service and returns `BulkHoldingsUploadResponse` summarizing records processed.

## Chat (`/chat`)
- `POST /` — requires auth; accepts `ChatRequest` (message text, optional file + history, optional LLM model) and returns `ChatResponse` with the agent reply. Uses per-request UUID thread IDs in service layer.

## WhatsApp (`/webhooks` + `/api/whatsapp`)
- `GET /webhooks/whatsapp` — **Public**; Facebook verification handshake (returns challenge when `hub.verify_token` matches config).  
- `POST /webhooks/whatsapp` — **Public**; validates `X-Hub-Signature-256`, parses `WhatsAppWebhook`, passes to `WhatsAppService.process_webhook`. Always returns 200 `{ok: true}` on downstream errors to avoid retries.  
- `POST /api/whatsapp/send-text` — service-to-service endpoint; sends free-form text using `SendTextRequest`, returns Meta API echo (`SendTextResponse`).  
- `POST /api/whatsapp/send-template` — similar but for template messages, payload `SendTemplateRequest`.  
- `POST /api/whatsapp/connect-intent` — requires auth; creates a short-lived linking code & deeplink (`ConnectIntentResponse`).  
- `DELETE /api/whatsapp/{integration_id}` — requires auth; removes stored WhatsApp metadata for the authenticated user.

## Kite Connect (`/kite`)
- `GET /login` — requires auth; redirects user to Zerodha’s OAuth.  
- `GET /callback` — **Public**; Zerodha redirect target. Exchanges `request_token` for session (needs `KITE_API_SECRET`), stores sanitized session per user, redirects back to frontend with status query.  
- `GET /token` — requires auth; returns `{connected, session?}` based on in-memory map.  
- `GET /status` — **Public**; minimal debugging info `{connected, user_id}` based on optional cookie.  
- `GET /holdings` — requires auth; proxies Kite’s holdings endpoint using stored access token, returns JSON-encoded holdings list.

## Health
- `GET /healthz` — unauthenticated liveness probe returning `{status, service}`.
