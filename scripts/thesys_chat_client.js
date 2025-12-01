/**
 * Minimal Node client to stream from /api/thesys/chat.
 * Configure env vars:
 *  - THESYS_CHAT_URL (default: http://localhost:8000/api/thesys/chat)
 *  - THESYS_AUTH_COOKIE (e.g., "access_token=...") if your API requires cookie auth
 *  - THESYS_THREAD_ID (optional; default: thread-123)
 *  - THESYS_PROMPT (optional; default prompt text)
 */

const url = process.env.THESYS_CHAT_URL ?? "http://localhost:8000/api/thesys/chat";
const authCookie = process.env.THESYS_AUTH_COOKIE;
const threadId = process.env.THESYS_THREAD_ID ?? "thread-123";
const responseId = `resp-${Date.now()}`;

const body = {
  prompt: {
    role: "user",
    content:
      process.env.THESYS_PROMPT ??
      "Give me loss-making shares in my portfolio and total loss for each.",
  },
  threadId,
  responseId,
};

async function main() {
  const headers = { "Content-Type": "application/json" };
  if (authCookie) headers.Cookie = authCookie;

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Request failed: HTTP ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let accumulated = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    process.stdout.write(chunk);
    accumulated += chunk;
  }

  console.log("\n\n--- complete ---");
  console.log(accumulated);
}

main().catch((err) => {
  console.error("Error:", err);
  process.exit(1);
});
