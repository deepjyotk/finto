## TODOs

- [ ] Test the screener analysis HITL form with different default values.
- [ ] Edge Case: Handle no portfolio Data, appropriate handling in financial analysis node (Must not restrict user from asking general finance question not on portfolio).
- [ ] A2-UI Bug:
    - [ ] A2-UI: CDN not getting displayed when query goes to "web_search_node"
- [ ] Manual Testing: 
    - Game feature:
        - Don't display non trading days on the game feature. Bad user experience :(

- [ ] Users to create portfolio buckets, and allow users to select buckets from UI 
when asking questions. (For e.g: "Do financial analysis for stocks in @my_bucket")

- [ ] Filing:
    - Run a cron job daily to fetch the latest filings from the SEC and other regulatory bodies.
    - Save in DB.
    - Use the filings to create alerts for specific events.
    - Index the filings in a vector database.
    - Put in the appropriate context whenever necessary


- [ ] Alert/Notifications Feature:
    - Notifications:
        - As a user, I should be able to get promotional notifications/announcements from the platform.

    - Alerts:
        - As a user, I should be able to create custom alerts for specific events; daily, weekly, monthly, etc.
        - Events can be:
            - Earnings
            - Business Updates
            - Regulatory Updates
            - Corporate Actions
            - M&A
            - Distress Events
            - Macro Events
            - Policy Events
        - Alerts should be sent to the user's email/whatsapp as well as on the platform (Web).
        - Flow:
            - User creates an alert with keywords, frequency, and channel(s).
            - Save in DB
            - Use 

(NOTE: celery workers with redis queue can be used with cron jobs to fetch the latest filings and create alerts.)
