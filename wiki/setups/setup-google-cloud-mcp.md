Configured in your global Cursor MCP config at `~/.cursor/mcp.json` by adding:

- `gcloud` server with `command: "npx"`
- args: `["-y", "@google-cloud/gcloud-mcp"]`

That means it’ll be available across all workspaces in Cursor.

### Next steps to make it work

1. Ensure prerequisites are installed:
   - Node.js `20+`
   - `gcloud` CLI

2. Authenticate `gcloud` in your terminal:
   - `gcloud auth login`
   - `gcloud config set project finto-477904`

3. Restart Cursor (or reload MCP servers) so it picks up the new config.

4. Test in Cursor by asking the assistant something like:
   - “List my GCP projects using gcloud MCP.”

### Optional hardening (recommended)

- Use least privilege by impersonating a service account in your local gcloud config for MCP usage, instead of a broad personal account.

If you want, I can also switch this to **project-local** config (`.cursor/mcp.json`) instead of global.