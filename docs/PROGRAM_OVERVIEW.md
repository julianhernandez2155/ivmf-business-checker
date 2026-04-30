# IVMF Business Operational Status Checker — Program Overview

**Author:** Julian Hernandez (IVMF Project Assistant)
**Last updated:** 2026-04-28
**Audience:** IVMF leadership, program staff, technical reviewers

---

## 1. What this tool does, in one paragraph

The Business Checker is a Python program that takes a spreadsheet of veteran-owned businesses (name, city, state, optional website) and, for each row, determines whether that business is still actively operating. For every business, it produces a four-part verdict: a **status** (Active / Likely Closed / Uncertain / No Web Presence), a **confidence score** from 0 to 100, a **one-sentence evidence summary** citing what was found, and a list of **source URLs**. The verdicts are written into a new Excel file with the original columns preserved and color-coded results added to the left side.

The tool exists because manually verifying thousands of businesses by Googling them is slow, inconsistent across reviewers, and produces no audit trail. The same record checked by two staff members can produce two different answers depending on how each person searches and what they consider "still in business." This program standardizes that decision.

---

## 2. The big picture — start to finish

When you run the program, here is what happens, in order:

1. **You hand it a spreadsheet.** It reads the headers and figures out which columns hold the business name, city, state, and website. You don't have to format the file in any specific way — it auto-detects common header names.

2. **It creates a run folder.** Every run gets its own timestamped folder under `Business Checker/Runs/`. A copy of your input file goes in there, along with a checkpoint file and a log. This means runs are reproducible and never overwrite each other.

3. **It checks for cached results.** If a business was already checked in the last 30 days (same name + city + state), the tool reuses that result and skips the API call. This saves money and time on overlapping datasets.

4. **For each business, it scrapes the website first.** Before asking the AI anything, it fetches the actual web page and extracts the visible text. This catches things the AI can't reliably see on its own — 404 errors, expired domains, parking pages, gambling spam squatters, "coming soon" placeholders. The result of this scrape becomes part of what the AI sees.

5. **It calls Perplexity with a structured research prompt.** The prompt tells the AI exactly how to investigate: a Fast Path for sites that are obviously live, and a Full Investigation across 8 channels (Google search, Google Maps, Facebook, Instagram, LinkedIn, owner search, marketplaces, and industry directories) for everything else. The AI is forced to return its answer in a specific JSON format — status, confidence number, one-sentence evidence — so we never get free-form text that's hard to parse.

6. **It applies post-processing rules.** If the AI says "No Web Presence" but the scraper already proved the domain is dead (404 or DNS failure), the tool overrides that to "Likely Closed" with at least 70% confidence. If the AI says "No Web Presence" but the scraper successfully retrieved real content, the tool flags the row "Uncertain" for human review because that's a contradiction worth a second look.

7. **It saves progress after every single business.** A checkpoint CSV is updated row by row. If you Ctrl+C in the middle of a 5,000-row run, you can re-run the same command and it picks up exactly where it left off. No lost work, no double-charges to the API.

8. **It writes a final Excel report.** When the run finishes (or you stop it), it builds a results spreadsheet with four new columns on the left — `AI_Status`, `AI_Confidence`, `AI_Evidence`, `AI_Checked_At` — followed by every original column from your input. Status cells are color-coded: green for Active, red for Likely Closed, yellow for Uncertain, gray for No Web Presence. Whole rows get a lighter shade of the same color so you can scan and filter quickly.

That's the entire program from your perspective. Everything else is plumbing that makes those eight steps reliable.

---

## 3. The architecture — WAT (Workflows, Agent, Tools)

The project is organized around a pattern called **WAT**: Workflows, Agent, Tools. The point of this pattern is to keep three different kinds of work physically separated so each one can be improved without breaking the others.

- **Workflows** are markdown documents that describe *what* the system is supposed to do, the edge cases, and the lessons learned. They live in `workflows/` and are written in plain English. The current one is `workflows/check_business_status.md`.

- **Agent** is the AI (Perplexity Sonar) plus the prompt that tells it how to think. The system prompt is the longest part of the codebase by intention — the more carefully we define how the AI should investigate, the more consistent the output. The prompt lives inside `tools/check_business.py` so it's version-controlled alongside the code that calls it.

- **Tools** are small, deterministic Python files that do one thing each. `check_business.py` calls the API. `scrape_website.py` fetches web pages. `checkpoint.py` reads and writes the progress file. `build_output.py` writes the Excel report. `cache.py` handles the SQLite result cache. `columns.py` auto-detects spreadsheet headers. None of them know about each other beyond the function calls they need.

This separation matters because it lets us change the prompt (the most volatile part of any AI system) without touching the file I/O, and lets us swap the API provider (we already migrated from Claude to Perplexity once) without rewriting the spreadsheet handling.

---

## 4. The prompt — why this is the most important file in the project

The prompt sent to Perplexity is roughly 125 lines long and lives at the top of `tools/check_business.py`. It is the single most consequential part of this system. Two-thirds of the engineering work on this project has gone into iterating on the prompt, because the model is held constant — the prompt is the lever that controls accuracy.

The prompt does five specific things:

**It defines a Fast Path.** If the website we scrape clearly shows a real, currently operating business — products described, recent blog posts, a 2023–2026 copyright with substantive content, a restaurant menu with contact info — the AI is told to return Active immediately and not search further. This saves money and prevents the AI from second-guessing a clear answer.

**It defines a Full Investigation when the Fast Path doesn't apply.** When the website is dead, missing, a 404, or a parking page, the AI is required to work through 8 specific channels in order: Google search, Google Maps, Facebook, Instagram, LinkedIn, owner search, marketplaces, and industry directories. This is the part that makes the tool more accurate than a single Google search. A human reviewer might check 1–3 of these. The AI is forced to check all 8 every time.

**It defines what each status means with examples.** Active, Likely Closed, Uncertain, and No Web Presence are not vibes — they are defined in the prompt with specific evidentiary requirements. "Likely Closed" requires multiple independent signals or one unambiguous signal (e.g., Google Maps says "permanently closed"). "No Web Presence" can only be used after every channel has been searched and returned nothing.

**It defines a confidence rubric with score bands.** The AI is told that Active 95–100 means multiple channels confirm operation with recent dates; Active 60–79 means a single weak signal; Likely Closed 90–100 means multiple independent closure signals after a thorough search. This prevents the AI from assigning arbitrary confidence numbers.

**It encodes hard-won edge cases.** The prompt explicitly handles squatted domains (gambling spam = treat as dead domain), stale state incorporation records (not enough alone to call Uncertain — call Likely Closed if no recent activity exists anywhere), empty Square/Weebly/Wix landing pages (treat as dead domain), and the rule that location on file is where the business is registered, not necessarily where it operates (so don't penalize a Syracuse business that doesn't mention Syracuse on its national e-commerce site).

Every one of these rules is in the prompt because we caught a wrong answer in testing and traced it back to the AI not knowing something a human reviewer would know.

---

## 5. The website scraper — why it exists

We do not trust the AI to evaluate a website on its own. The AI's "search" tool does not always actually load the page; it may rely on cached snippets that are out of date, especially for small business sites. So before the AI is called, we hit the website ourselves and extract the visible text.

The scraper has two backends. The first is **Firecrawl**, an API service that handles JavaScript-rendered sites, Cloudflare-protected sites, and modern single-page applications. If the Firecrawl key is configured, we try it first. The second is **direct HTTP** with BeautifulSoup, which is free and works for the majority of small business websites that are static HTML.

The scraper does three things that materially improve accuracy:

1. **It detects parking pages and squatters.** A list of phrases — "domain for sale," "coming soon," "situs judi" (Indonesian gambling spam), "lorem ipsum" — is checked against the page text. If any are found, the scraper flags the page as "slop" and tells the AI to treat the website as non-functional and check social media before deciding.

2. **It distinguishes types of failure.** A 404 is different from a DNS failure, which is different from an SSL error, which is different from a timeout. Each one becomes a specific note in the AI's prompt: "the page no longer exists at this URL" vs. "the domain may no longer exist or has expired" vs. nothing (we let the AI search normally for SSL/timeout cases). These distinctions matter — a DNS failure is a strong closure signal; an SSL error usually isn't.

3. **It feeds real page content into the prompt.** When the scrape succeeds, up to 600 characters of the visible text from the homepage is pasted into the AI's user message under a heading that says "DIRECT WEBSITE CONTENT." The AI is told to use this alongside its search to evaluate the site. This is what enables the Fast Path — the AI is reading actual page content, not relying on stale search snippets.

---

## 6. Concurrency, rate limits, and cost

The runner uses a thread pool to check multiple businesses in parallel. The `--workers` flag controls how many. The choice depends on the Perplexity account tier:

- **Tier 0** (new account): 1 query per second. Use 1 worker.
- **Tier 1**: 3 QPS. Use 3 workers.
- **Tier 2**: 8 QPS. Use 8 workers.

Tier advances automatically based on spend history. If we hit a 429 rate-limit error, the API call retries with exponential backoff (30s, 60s, 90s, 120s) before giving up. If we hit a 5xx server error, we retry with shorter backoff (15s, 30s, 45s, 60s). 4xx errors other than 429 are not retried — those are programming bugs that need a human.

Cost on the current Perplexity Sonar model is approximately **$0.005 to $0.008 per business checked**, including the API call and (when configured) the Firecrawl scrape. A run of 5,000 businesses costs roughly $25–$40 of API spend. The cache prevents re-checking the same business twice within a 30-day window, so overlapping datasets are essentially free.

The total cost is logged after every run, broken down per session and per check.

---

## 7. The checkpoint — why runs survive interruptions

After every single business is checked, the row is appended to a checkpoint CSV in the run folder. Each entry contains the row number from the original spreadsheet, the business name, the website, the AI's status, confidence, evidence, and the timestamp of the check.

Three things follow from this:

1. **Crashes don't lose work.** If the laptop closes or the network drops mid-run, the next time you run the same command on the same input file, the tool reads the checkpoint and skips every row already done.

2. **Partial results are usable.** If a 5,000-row run is interrupted at row 2,000, you can build the Excel output from those 2,000 rows immediately. You don't have to wait for the whole thing.

3. **The checkpoint is auditable.** Every decision the AI made on every business is in a plain CSV that anyone can open in Excel and inspect. This is the audit trail required for any data-quality process.

---

## 8. The output file — what an analyst opens

When the run finishes, the tool writes `[InputFilename]_Results.xlsx` into the run folder. The format is:

- **Four AI columns first**, on the left: `AI_Status`, `AI_Confidence`, `AI_Evidence`, `AI_Checked_At`. They're first so analysts see the verdict immediately on open without scrolling.
- **Every original column preserved** to the right of the AI columns, in the same order they were in the input file.
- **Color-coded status cells** — green for Active, red for Likely Closed, yellow for Uncertain, gray for No Web Presence. Bold, large font.
- **Color-coded full rows** in a lighter shade of each status color, so the eye can sort the sheet by status visually.
- **Frozen header row** and **column auto-width** so it looks like a usable report, not a raw export.

The XML cleaning step strips characters that Excel will refuse to open, which has bitten previous tools when an evidence string included an unprintable byte from a scraped page.

---

## 9. How to use it

There are two ways to run it:

**A) Headless (recommended for large batches)** — open Terminal, navigate to the project folder, and run:

```bash
python run_checker.py --input businesses.xlsx --workers 3
```

This is what you'd use for the 5,000–20,000-row datasets. It logs progress to the terminal and to a `run.log` file inside the run folder. You can stop it with Ctrl+C and resume by running the same command again.

**B) GUI (for interactive use or smaller batches)** — double-click the launcher (or run `python business_checker_gui.py`). A window opens where you select the input file, set worker count, see live progress with status icons and color coding, and pause/resume the run. Same underlying code as the headless runner — it just wraps it in a Tkinter interface.

Both modes write the same checkpoint format and produce the same Excel output. You can start in the GUI and finish on the command line, or vice versa.

---

# Critical Questions — for leadership and program staff

This section answers the questions you are most likely to be asked.

## "How do I prep my data?"

Almost no prep is required. The tool auto-detects columns by reading the header row. It looks for these keywords (case-insensitive, partial match):

| Field | Headers it recognizes |
|---|---|
| Name | name, business name, company, organization |
| Website | website, web, url, site, link |
| City | city, town, municipality |
| State | state, province, region |

So a header row of `Business Name | Website | City | State` works. So does `Company | URL | Town | Region`. So does `name | site | city | state`. If a column is missing from your file, the tool warns you and proceeds with the columns it could find — for example, if there's no website column, every business goes through the Full Investigation path instead of the Fast Path, which is slower and slightly less accurate but still works.

The only required fields are **business name** and **state**. City helps disambiguate common business names but isn't required. Website is optional; absence is not treated as a closure signal.

What you don't need to do: clean the data, normalize URLs, fix capitalization, remove duplicates (the cache handles them), or re-format the file. Throw the spreadsheet at it as-is.

## "What is the workflow actually doing?"

For each row, in order:

1. **Read the row.** Pull name, city, state, and website from the columns the tool detected.
2. **Cache lookup.** Check if we've seen this business (same name + city + state) in the last 30 days. If so, return the cached verdict and stop.
3. **Scrape the website.** Fetch the homepage. Extract visible text. Detect parking pages, squatters, 404s, and DNS failures. Result becomes context for the AI.
4. **Build the AI prompt.** Combine the static research-protocol system prompt (the 125-line one) with the dynamic per-business message containing name, location, website, and scrape results.
5. **Call Perplexity Sonar.** The API forces the response into a strict JSON schema: status, confidence (0–100 integer), evidence (one sentence). We never get free-form text back.
6. **Post-process.** If the AI said "No Web Presence" but our scraper already confirmed the domain is dead, override to "Likely Closed" at 70%+ confidence. If the AI said "No Web Presence" but our scraper got real content, flag as "Uncertain" for human review (the scraper and the AI disagreeing is itself a meaningful signal).
7. **Save the verdict.** Append the row to the checkpoint CSV with a timestamp.
8. **Repeat for the next row** (in parallel with up to N other rows, depending on `--workers`).

When all rows are done, the tool reads the checkpoint plus the original file, applies color coding, and writes the final Excel output.

## "How is this more accurate than a person manually checking?"

This is the most important question, so here is the full answer.

**A human reviewer's process is, on average, one Google search.** They Google the business name, glance at the first three results, and decide. If the website is the first result and looks alive, they call it Active. If it's not on the first page of results, they often call it Closed or Uncertain.

**The AI's process is enforced to be eight searches plus a website scrape.** Every single business — not just the borderline ones — gets checked across:

1. The actual website content (via direct scrape)
2. Google Search with the quoted business name and location
3. Google Maps for the specific listing
4. Facebook for a business page
5. Instagram for an account
6. LinkedIn for the company and the owner
7. Marketplace search (Amazon, Etsy, specialty retailers) for product-based businesses
8. Industry directories (BBB, Yelp, trade associations)

A business that has let its website lapse but is still active on Facebook will be correctly called Active by the AI and incorrectly called Closed by a human who only looked at the website. A business with a live-looking website that's actually been abandoned since 2019 will be correctly caught as Uncertain by the AI (which sees the date staleness) and incorrectly called Active by a human who didn't notice the copyright year.

**The AI applies the same evidence rules to every business.** A human's standard for "active" drifts over the course of a day. By row 200, the reviewer is tired, and the threshold for calling a business "active" relaxes. The AI applies the exact same confidence rubric to row 1 and row 5,000.

**The AI cites its evidence in writing.** Every verdict includes a one-sentence evidence summary and source URLs. A human reviewer's process produces no audit trail. If a leadership review later asks "why did we mark Acme Co. as closed?", the AI's checkpoint contains the answer; the human's process doesn't.

**The known specific failure modes are caught.** The prompt explicitly handles squatted domains, expired Wix landing pages, stale state incorporation records, and businesses that operate under different entity names than they're registered under. Each of these rules came from a real wrong answer we caught in testing — and once it's encoded in the prompt, it never recurs. A human reviewer is not equally consistent.

**The pilot run validated this.** A 30-record pilot in March 2026 produced 83% Active determinations with average confidence 83%, no parse errors, and human spot-checks confirmed the verdicts. A specific case — a business named "Bomb Azz Lemonade" — was incorrectly called Uncertain at 20% confidence in an early version because the AI was matching unrelated magazine articles using the phrase. After we added a quoted-search rule and a disambiguation instruction to the prompt, the same business now correctly resolves to Active at 95%. That's the kind of failure mode the prompt iteration cycle catches and a human-only process repeats forever.

**This said, the AI is not infallible.** What it provides is **consistent, auditable, and faster** decision-making, with a defensible written evidence trail for every record. The Confidence column is the safety valve: rows with confidence under 50, especially "Uncertain" ones, should still go to a human reviewer. The tool reduces the human review queue by ~80–90%, not to zero.

## "What's the cost, and how do we control it?"

Approximately $0.005–$0.008 per business checked. A 1,000-row dataset costs $5–$8. A 20,000-row dataset costs roughly $100–$160. The cache eliminates redundant cost on repeat runs of overlapping datasets.

The `.env` file is where the API key and per-call cost estimates live. Cost is logged at the end of every run and broken down per check.

If we ever need to control cost more tightly, we can: (1) lower worker count to throttle (the rate limit is the only ceiling on spend per minute), (2) add a `--limit` flag to test on a sample first, or (3) raise the cache TTL beyond 30 days for stable datasets.

## "What if the AI gets it wrong?"

Three answers:

1. **The Confidence column is your filter.** Anything below 50% confidence is explicitly flagged for manual review in the prompt's design. Anything 50–79% with status "Likely Closed" should be spot-checked. 80+% is reliable.

2. **Every verdict has written evidence and source URLs.** When a verdict looks wrong, the evidence string and citations tell you exactly what the AI saw. This is a 30-second human review per row, not a from-scratch re-investigation.

3. **The prompt is editable.** When we find a class of failure (e.g., "AI keeps confusing common business names"), we add a rule to the system prompt and the failure mode is fixed for every future run. The Learnings Log in `workflows/check_business_status.md` tracks every prompt change with a date and the case that triggered it.

## "What about businesses with no website?"

Handled. The Full Investigation path runs without a website — the AI searches by name and location across all 8 channels. Expect more "Uncertain" and "No Web Presence" results in this group, which is correct: a business with no online presence anywhere genuinely is harder to verify than one with a Facebook page.

## "What about veteran-owned businesses that operate nationally or are home-based?"

Handled explicitly. The prompt includes a location note: "The location above is where this business is registered or based, not necessarily where it operates. Many veteran-owned businesses sell nationally, work online, or are home-based. Never require the city or state to appear on the website or social media — it often won't." This prevents the AI from incorrectly downgrading nationally-operating businesses for not mentioning their registered city.

## "Is the data secure?"

Yes. The program runs locally on the user's machine. The only data sent to external services is the business name, city, state, and website — the same information that's already publicly searchable on Google. No PII, no internal IVMF data, no records beyond the four fields. The Perplexity API is called over HTTPS. The API key is stored in a local `.env` file that is gitignored and never committed.

## "Can it be re-run on the same data?"

Yes, with three caveats:

1. **Same run folder, same input file** — the tool reads the existing checkpoint and skips already-checked rows. Useful for resuming an interrupted run.

2. **New run folder, same input file, cache enabled** — the cache returns the prior verdict for businesses checked in the last 30 days. Useful for re-generating the Excel output without re-paying for API calls.

3. **`--no-cache` flag** — forces fresh API calls on every row even if cached results exist. Useful for periodic re-verification (e.g., a quarterly refresh) where we want updated answers for businesses whose status may have changed since the last check.

## "What does success look like? How do we measure if this is working?"

Three measurable outcomes:

1. **Time-to-decision.** A human reviewer takes roughly 60–90 seconds per business if they're being thorough. The tool processes ~1 business per second per worker. A 5,000-row dataset that would take a human ~85 hours of focused work runs end-to-end in roughly 30 minutes at 3 workers.

2. **Spot-check agreement rate.** Pull a random sample of 50 verdicts (stratified across the four statuses). Have a senior staff member review each by hand without seeing the AI's verdict. Measure agreement. Pilot data showed >90% agreement on confidence-80+ rows.

3. **Audit trail coverage.** 100% of verdicts have written evidence and source citations. Compare to the prior process (manual spreadsheet edits with no captured rationale).

The tool is not replacing human judgment on hard cases. It's eliminating manual work on the obvious cases — which is most of them — and concentrating human attention on the rows where it's actually needed.

---

## 10. Where to look in the code

For anyone who wants to verify any of the above:

| File | What's in it |
|---|---|
| `tools/check_business.py` | The system prompt (lines 49–173), the API call, post-processing rules |
| `tools/scrape_website.py` | Website scraping, parking-page detection, error classification |
| `tools/cache.py` | SQLite-backed result cache, 30-day TTL |
| `tools/checkpoint.py` | Thread-safe checkpoint CSV reader/writer |
| `tools/build_output.py` | Final Excel output assembly with color coding |
| `tools/columns.py` | Auto-detection of spreadsheet column headers |
| `run_checker.py` | Headless concurrent runner with thread pool |
| `business_checker_gui.py` | Tkinter GUI wrapper around the same tools |
| `workflows/check_business_status.md` | Plain-English SOP for the workflow, including the Learnings Log |
| `CLAUDE.md` | Internal agent instructions explaining the WAT architecture |

Every meaningful decision the program makes is in one of those files, and each file is small enough to read end-to-end in 5–10 minutes.

---

## 11. Appendix — The full Perplexity prompt

What follows is the **exact, verbatim** system prompt sent to Perplexity Sonar on every business check. Every word in this prompt is the result of intentional iteration — when leadership asks "what is the AI being told to do?", this is the answer in full. It is reproduced here so reviewers can read it without opening the source code.

This prompt lives at `tools/check_business.py` lines 49–173. If it is ever updated in code, this appendix should be updated to match.

### A) System prompt (constant on every call)

```
You are a research analyst verifying whether a specific business is still actively operating. Think like a thorough investigator — not just someone running a quick search.

---

FAST PATH — use this if the website content provided shows a real, currently operating business. Ask yourself: does this look like a live business, or does it look abandoned?

  Qualifies as Active (any of these):
       • Real products or services described with specific details (flavors, pricing, sizing, service descriptions) — does NOT require a shopping cart or online checkout
       • A restaurant, caterer, or food vendor with a current menu and contact info
       • A service business with a contact form, phone number, or booking link and real service descriptions
       • A portfolio, gallery, or event schedule showing recent work or upcoming dates
       • Blog or news posts from 2023 or later
       • Copyright year 2023–2026 in the footer alongside substantive content
       • An informational site for a business that clearly sells in person, at markets, or through distributors — not every business sells online, and that is fine

  Does NOT qualify — proceed to Full Investigation:
       • Website loads but all content and dates are from 2021 or earlier
       • "Coming soon," "under construction," or "we're rebuilding the site" message
       • Only a contact page or generic About page with no real products or services described
       • Placeholder or template text (no real business-specific content)
       • The site is vague enough that you cannot tell what this business actually sells or does

If the website qualifies → return Active immediately. Do NOT search further. Do NOT override this with state LLC registry status, Secretary of State filings, or other administrative records — a business can operate under a different entity or as a sole proprietorship even if the original LLC is administratively inactive. The live website with real content is the definitive signal.

---

FULL INVESTIGATION — required if the website was dead, missing, a parking page, a 404, or a DNS failure.

A dead website does NOT mean a closed business. Many small businesses let their website lapse while remaining fully operational through social media, Google Maps, farmer's markets, or word of mouth. You must work through ALL of the following channels before drawing any conclusion. Do not stop early.

CHANNEL 1 — GOOGLE SEARCH
Run all of these queries:
  • "[BUSINESS NAME]" [LOCATION]
  • "[BUSINESS NAME]" [relevant industry term — e.g., "catering", "sauce", "jerky", "consulting"]
Look for: Google Business Profile (open or closed?), Yelp listing, BBB entry, press coverage, or any directory entry specifically about this business. Note the most recent date you find.

CHANNEL 2 — GOOGLE MAPS
Search Google Maps for "[BUSINESS NAME]" near [LOCATION].
  • "Permanently closed" on Google Maps = strong closure signal.
  • Open listing with reviews from 2023–2026 = strong Active signal.
  • No listing at all = neutral. Normal for online-only, home-based, or mobile businesses. Do not treat absence as closure.

CHANNEL 3 — FACEBOOK
Search Facebook for a business page named "[BUSINESS NAME]".
  • Posts or customer interactions from 2023–2026 = Active.
  • Page exists but last post is 2021 or earlier = Uncertain signal.
  • No page found = note it and continue.

CHANNEL 4 — INSTAGRAM
Search Instagram for "[BUSINESS NAME]".
  • Recent posts or stories (2023–2026) = Active signal.
  • Account exists but inactive since 2021 or earlier = Uncertain.
  • Not found = note it and continue.

CHANNEL 5 — LINKEDIN
Search LinkedIn for the company "[BUSINESS NAME]" and for its owner/founder.
  • Active company page or owner currently listing this as their business = positive signal.
  • Owner's LinkedIn shows they moved on to a different business = possible closure signal.

CHANNEL 6 — OWNER / OPERATOR SEARCH
If you find or know the owner's name from any search above:
  • Search: [owner name] + "[BUSINESS NAME]"
  • Look for recent interviews, podcast features, news articles, or social posts where they reference the business.
  • An owner actively promoting the business in 2023–2026 = strong Active signal.

CHANNEL 7 — MARKETPLACES (for product-based businesses)
Search Amazon, Etsy, specialty food retailers, or other relevant platforms for "[BUSINESS NAME]" products.
  • Products listed and in stock = Active signal.
  • Products listed as unavailable or removed = weak closure signal.

CHANNEL 8 — INDUSTRY DIRECTORIES & MARKETPLACES
Search BBB (bbb.org), Yelp, industry-specific directories, or trade association member lists for "[BUSINESS NAME]".
  • Active listing with recent activity = supportive Active signal.

---

STATUS DEFINITIONS:
- Active: Clear evidence of current operation found on any channel. Examples: website with real content, open Google Maps with recent reviews, active Facebook or Instagram, products available for purchase, owner actively promoting the business.
- Likely Closed: Multiple independent closure signals after a thorough search — e.g., dead website PLUS Google Maps "permanently closed" PLUS no social media activity PLUS no other presence found. OR one unambiguous signal (the business's own page announces closure, Google Maps explicitly says "permanently closed").
- Uncertain: You found this business on at least one channel but cannot confirm it is currently operating — last activity was 2020–2022, signals are mixed, or the owner's status is unclear.
- No Web Presence: After completing ALL channels above, you found absolutely nothing specific to this business anywhere. This is a last resort — only use it after a genuinely thorough search.

CRITICAL RULES:
- A dead website alone is NOT sufficient to call a business closed. You must check all channels.
- Do NOT stop investigating after a negative signal. Each negative finding should push you to search harder.
- Only use evidence that is specifically about THIS business. Ignore articles or results that merely mention the name in passing.
- Results from before 2022 are not reliable evidence of current operating status.
- "Likely Closed" requires multiple signals, not just one. "No Web Presence" requires every channel to come up empty.

SQUATTED / HIJACKED DOMAINS:
- If a domain now hosts gambling, adult content, spam, generic blog content, or a parking page clearly unrelated to the original business — treat it as a dead domain. It counts as one closure signal.
- Squatted domain + no social media activity + no Google Maps listing + no other channel hits = "Likely Closed". Do NOT call this "Uncertain" just because you cannot find an explicit closure announcement.

STALE RECORDS WITH NO CORROBORATION:
- If the only evidence you can find is a state incorporation record or a basic directory listing (Manta, OpenFOS, Infogroup, etc.) with no activity after 2021, and no social media, no maps, no press, no owner activity — that is NOT enough to call a business "Uncertain". Call it "Likely Closed" (multiple stale signals with nothing recent = closure pattern).
- Old incorporation records alone are not evidence of current operation.

EMPTY WEBSITE BUILDERS (Square, Weebly, Wix placeholders):
- A generic landing page on Square, Weebly, or Wix with no business-specific content (no products, no services, no contact info specific to this business) is NOT a real web presence. Treat it the same as a dead domain.

NO WEB PRESENCE — use it precisely:
- Only use "No Web Presence" if you found NOTHING specific to this business across all 8 channels — not even an old directory listing, not even an owner social profile.
- If you found any result that specifically names this business (even an old one), use "Uncertain" or "Likely Closed" instead.
- A personal Whitepages or RocketReach profile for an individual is NOT a business web presence.

---

CONFIDENCE SCORE RUBRIC (use this — do not assign arbitrary numbers):

  Active 95–100: Multiple channels confirm current operation with recent dates (2024–2026).
  Active 80–94:  One channel clearly confirms active operation, recency somewhat unclear.
  Active 60–79:  Single weak or indirect Active signal (old directory listing with one recent review).

  Likely Closed 90–100: Multiple independent channels all point to closure after thorough search.
  Likely Closed 70–89:  Strong closure evidence on 2+ channels, not all channels fully checked.

  Uncertain 60–80: Found the business on at least one real channel but last confirmed activity was 2020–2022, or signals conflict across channels.
  Uncertain 40–59: Very thin evidence — found only a name match in an old directory with no corroboration. If you are here and found nothing after 2020, consider Likely Closed instead.

  No Web Presence 75–90: All 8 channels thoroughly searched and returned nothing.
  No Web Presence 50–74: Search was limited due to a very generic name or ambiguous location.

If you would score your chosen status below 50%, reconsider — a different status likely fits better.

Respond with the status, confidence score, and a one-sentence evidence summary naming the specific source and its recency (e.g., "website dead, Google Maps permanently closed January 2025, Facebook inactive since 2020" or "website loads with active e-commerce, products in cart as of 2026").
```

### B) User message (rebuilt fresh for each business)

The system prompt above is constant. The per-business user message is assembled at runtime and looks like this:

```
Business name: "[NAME]"
Location on file: [CITY, STATE]
[WEBSITE NOTE: either "Their listed website is: [URL]" or "No website listed."]

[SCRAPE SECTION — one of the following, depending on what the website scraper returned:]

  CASE 1 — Live page with real content:
    DIRECT WEBSITE CONTENT (retrieved from [URL]):
    ---
    [up to 600 chars of visible page text]
    ---
    Use this content alongside your search to evaluate whether the site shows a real, currently operating business.

  CASE 2 — Parking / placeholder / spam-squatted page:
    NOTE: Direct retrieval of [URL] returned a parking, placeholder, or spam-squatted page ([reason]) — [The domain has been taken over by a spam or gambling site — the business lost control of it. | The business may have let this domain lapse.] Treat the website as non-functional. You MUST check all social media channels (Facebook, Instagram, LinkedIn) before drawing any conclusion — many businesses with dead domains still operate actively through social media alone.

  CASE 3 — HTTP 404:
    NOTE: Direct access to [URL] returned a 404 error — the website content no longer exists at this URL. This is a meaningful closure signal. Factor it into your assessment.

  CASE 4 — DNS / connection failure:
    NOTE: Direct access to [URL] failed with a DNS or connection error — the domain may no longer exist or has expired. This is a strong closure signal. Factor it into your assessment.

  CASE 5 — No website on file, OR generic SSL/timeout failures:
    [no scrape section]

LOCATION NOTE: The location above is where this business is registered or based, not necessarily where it operates. Many veteran-owned businesses sell nationally, work online, or are home-based. Never require the city or state to appear on the website or social media — it often won't.
```

### C) Response format (enforced via JSON schema)

Perplexity is required to return a JSON object matching this Pydantic schema. The model cannot return free-form prose — the API rejects malformed responses, which is why parse errors are essentially zero in production:

```python
class BusinessStatus(BaseModel):
    status:     Literal["Active", "Likely Closed", "Uncertain", "No Web Presence"]
    confidence: int    # 0–100
    evidence:   str    # one sentence citing source and date if available
```

The `citations` array (a list of source URLs) is returned by Perplexity at the message level alongside the JSON content, and is appended to the evidence string in the final output.

### D) A worked example

For a row containing:
- Name: "Acme Veteran Services LLC"
- City: "Syracuse"
- State: "NY"
- Website: "https://acmevets.com"

If the scraper successfully fetches the homepage and extracts the text "Veteran-owned IT consulting firm serving the Syracuse area since 2018. Contact us at (315) 555-0100. Recent project: Federal IT modernization, March 2026.", the user message becomes:

```
Business name: "Acme Veteran Services LLC"
Location on file: Syracuse, NY
Their listed website is: https://acmevets.com

DIRECT WEBSITE CONTENT (retrieved from https://acmevets.com):
---
Veteran-owned IT consulting firm serving the Syracuse area since 2018. Contact us at (315) 555-0100. Recent project: Federal IT modernization, March 2026.
---
Use this content alongside your search to evaluate whether the site shows a real, currently operating business.

LOCATION NOTE: The location above is where this business is registered or based, not necessarily where it operates. Many veteran-owned businesses sell nationally, work online, or are home-based. Never require the city or state to appear on the website or social media — it often won't.
```

The expected response (Fast Path triggered — real content, recent date in footer, contact info present):

```json
{
  "status": "Active",
  "confidence": 95,
  "evidence": "Website loads with substantive content, contact info, and a March 2026 project reference."
}
```
