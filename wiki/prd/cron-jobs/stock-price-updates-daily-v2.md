
Read the stock-price-updates-daily-v1.md, this PRD will be extension of it:


1. My infra is hosted on GCP, and I want to have support for Cron Job that runs at 4 PM daily to trigger the daily_price_bars_1d_cron.py (obviously dont use this file, since we want to have api layer, but do use the src/cron-jobs/price-bars-1d/services/price_bars_1d_ingest.py to inject in our api layer...read below!) Basically, for the current date, when cron job is triggered, we wanna fetch the current day's price bars and upsert into the price_bars_1d table.


2. So, obviously, we need to expose some endpoint for the cron job to trigger.


3.A So, first create a new api endpoint in apis folder with prefix: /cron-jobs
  
  And create a new endpoint: /daily/
  Refer the existing infra.md file on existing gcloud infra that i have.


3.B So, currently, I've already enabled cloudscheduler. But, there's no job created yet.

  So, you need to appropriately create a new JOB: https://console.cloud.google.com/cloudscheduler?project=finto-477904 
  using gcloud MCP tools available. And basically refer the existing infra.md file to learn how the
  infrastructure is setup; so that you can call the endpoint that you created in 3.A
  To fill the values of scheduler, for mcp tool, refer the following:
  Use **POST** to your Cloud Run endpoint and, for testing, set it to **Allow unauthenticated** so you can verify it works quickly. Set the cron to **`30 10 * * 1-5`** with timezone **Asia/Kolkata** to trigger at **4 PM IST, Monday–Friday (no weekends)**.



Basically, "/daily/" should be a post trigger endpoint that gcloud scheduler will hit it.

4. Implementation of /daily:
  - Basically using DI inject the service: src/cron-jobs/price-bars-1d/services/price_bars_1d_ingest.py
  - And then call the service from the endpoint. (refresh_recent_daily function basically)
  - Use the same DI pattern, where we have deps.py a centralized place to inject the dependencies.
  - Basically, also create a repo layer, since we need to update the price_bars_1d table.; (inject this repo layer in the service)...just follow the existing coding style.

