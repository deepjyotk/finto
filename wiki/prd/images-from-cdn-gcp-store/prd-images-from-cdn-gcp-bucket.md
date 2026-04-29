So, for each company, I want to store its logo in a GCP bucket.

Since we’re a startup with very limited funds, we aim to use a free-tier CDN.

* So, we plan to use Cloudflare CDN.
* If the logo isn’t in the CDN, we fetch it from the GCP bucket.

Now, what I want:

- Now, for each company f

* Create a script at `scripts/logos-to-cdn-bucket/logos-to-cdn-bucket.py`.

* The script should take a list of company logos and upload them to both the Cloudflare CDN and the GCP bucket.

* If the GCP bucket doesn’t exist, create it using the GCP MCP server. Then update the `.env` file, `settings.py`, and `infra.md` in the wiki with the bucket name.

* Research how to upload to Cloudflare CDN and implement it. Add the required environment variables to `.env` and `settings.py`.

Keep the script simple, modular, and easy to understand. Install any required dependencies (e.g., for Cloudflare CDN or GCP, use the official `google-cloud` libraries).



Okay, so to write the script for: scripts/logos-to-cdn-bucket/logos-to-cdn-bucket.py,

Follow:
- fetch_symbols_from_in_equities, make the limit as optional argument, and default to all symbols.
- now, follow the same pattern as fetch_multibagg_company_logo_svg.py, But the only change is you have to not save the logs in the folder, but you
have to save the logo in the GCP bucket and also in the Cloudflare CDN.