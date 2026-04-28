The current A2UI implementation isn’t aligned with the official protocol.

We are not properly following A2UI’s architecture or component usage. For example, in `a2ui-catalog.tsx` we are using React, but not in the recommended way outlined in:

* [https://github.com/google/A2UI/tree/main/renderers/react](https://github.com/google/A2UI/tree/main/renderers/react)
* [https://github.com/google/A2UI](https://github.com/google/A2UI)
* [https://a2ui.org](https://a2ui.org)

Right now, we are creating custom components—but is that correct? I expected us to use the official A2UI libraries instead.

Please do deep research and confirm:

1. Are we using A2UI correctly in `explainly-frontend/`? Specifically, why don’t we see `@a2ui/react` or `@a2ui/web_core` in our UI code?
2. What exactly is wrong or non-standard in our current implementation, even if it works?



The backend code folder is: finto/*
The frontend code folder is: explainly-frontend/*