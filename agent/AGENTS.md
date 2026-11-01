
## How to respond to an error or a FIX verdict
1. No apologies, no praise, no filler words.
2. CHECK first: quote the exact assert or traceback line showing the issue. If evidence does not support it, state DISPUTED and show what you checked.
3. CAUSE in one sentence.
4. Minimal PATCH: only the affected file and function, as search/replace blocks. Do not rewrite passing files.
5. VERIFY: name which tests must pass now and which could break.
6. Do not repeat a failed fix: if identical to a previous attempt, change hypothesis and explain in one line.
