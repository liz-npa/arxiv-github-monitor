# arXiv → GitHub Monitor NVP Engineering Spec

**Goal:** Build a low-cost, stable monitoring system that discovers new arXiv papers, filters for papers with linked GitHub repositories, and continuously tracks those repositories for early implementation and adoption signals.

**Status:** NVP / MVP v0

**Primary success metric:** Each daily run produces a compact list of newly discovered papers with normalized GitHub repos, plus an updated watchlist of high-signal repos.

---

## 1. Problem Statement

The user wants a system that answers two questions continuously:

1. Which new arXiv papers are already accompanied by GitHub repos?
2. Among those repos, which ones show practical momentum and are worth watching?

This is not a general paper scraper. It is an early-signal system for **research with implementation potential**.

---

## 2. Product Scope

### In scope for NVP
- Pull new papers from selected arXiv categories.
- Normalize paper metadata into a local store.
- Extract GitHub repo URLs from paper metadata / abstract page / PDF fallback.
- Normalize repos to `owner/repo` keys.
- Poll GitHub regularly for repo health and growth signals.
- Produce one daily summary and one machine-readable snapshot.

### Out of scope for NVP
- Full-text semantic ranking of all papers.
- X / Reddit / Hacker News / Discord social listening.
- Training a custom scoring model.
- Browser-heavy scraping at scale.
- Real-time event streaming.

---

## 3. NVP Design Principles

1. **Official interfaces first**: prefer arXiv RSS/API and GitHub API over brittle scraping.
2. **Incremental by default**: only process new papers and tracked repos.
3. **Cheap first**: avoid paid APIs unless they unlock a clear gap.
4. **Defer expensive parsing**: only inspect PDF when simpler sources fail.
5. **Two-stage filtering**: first detect paper+repo; then score repo quality over time.

---

## 4. Source Strategy

## 4.1 arXiv ingestion

### Recommended primary pipeline
1. **RSS/Atom feeds** for discovery by subject area.
2. **arXiv API** for structured metadata enrichment.
3. **Abstract page HTML** for repo extraction.
4. **PDF parsing fallback** only for promising papers with no repo found upstream.

### Why this order
- RSS is stable, simple, and cheap for daily discovery.
- API gives better metadata than RSS without scraping.
- HTML can expose explicit GitHub links missing from API fields.
- PDF parsing is highest-maintenance and should be used sparingly.

### Initial categories
- `cs.LG`
- `cs.AI`
- `cs.CL`
- `cs.CV`
- `stat.ML`

Later add or remove categories based on noise.

---

## 4.2 GitHub ingestion

### Recommended primary pipeline
1. **REST API** for repo metadata polling.
2. **Optional GraphQL** later when watchlist size grows.
3. **No webhook assumption** for third-party public repos.

### Why REST first
- Simple to implement.
- Sufficient for hundreds of repos at NVP scale.
- Easy to debug and backfill.

---

## 5. Stability and Cost Comparison

## 5.1 arXiv data access options

### A. RSS / Atom feeds
**Use for:** daily discovery

**Pros**
- Official and stable.
- Very low implementation complexity.
- Near-zero runtime cost.
- Natural fit for cron-based incremental jobs.

**Cons**
- Limited metadata.
- Not enough by itself for reliable GitHub extraction.

**Decision:** yes, this is the discovery entry point.

---

### B. arXiv API (Atom XML)
**Use for:** metadata enrichment

**Pros**
- Official structured interface.
- Good for title, summary, categories, timestamps, authors.
- Free.

**Cons**
- XML parsing overhead.
- Should be rate-limited politely.
- Does not guarantee explicit repo URLs.

**Operational note**
- arXiv recommends adding ~3s delay when making repeated API calls.

**Decision:** yes, this is the metadata backbone.

---

### C. OAI-PMH
**Use for:** large archival syncs, not NVP

**Pros**
- Official harvesting interface.
- Good for long-term archive workflows.

**Cons**
- Heavier than needed.
- Not optimized for the user question: “what new papers with code should I watch?”
- Adds complexity without solving repo extraction.

**Decision:** no for NVP.

---

### D. HTML scraping / PDF parsing
**Use for:** repo extraction fallback

**Pros**
- Can find links hidden in page content or paper body.
- Covers cases where API metadata is insufficient.

**Cons**
- Most brittle approach.
- PDF extraction is noisy and higher-maintenance.
- More CPU and parsing complexity.

**Decision:** yes, but only as targeted fallback.

---

## 5.2 GitHub data access options

### A. REST API
**Use for:** NVP polling

**Pros**
- Straightforward implementation.
- Good enough for repo counts in the low hundreds.
- Supports all core fields needed for scoring.

**Cons**
- One repo can require multiple endpoint calls if overused.
- Need pacing to avoid secondary rate limits.

**Decision:** yes, default for NVP.

---

### B. GraphQL API
**Use for:** later optimization

**Pros**
- Better batching and field selection.
- More efficient for larger watchlists.

**Cons**
- More complex query construction and error handling.
- Not necessary for first shipping version.

**Decision:** defer until repo volume justifies it.

---

### C. GitHub web scraping
**Use for:** never by default

**Pros**
- None meaningful at NVP stage.

**Cons**
- Brittle.
- Unnecessary when APIs already expose required metadata.

**Decision:** do not use.

---

## 5.3 Cost summary

### arXiv
- RSS: free
- API: free
- HTML/PDF fallback: free if processed locally
- Main cost: engineering complexity, not API spend

### GitHub
- Unauthenticated REST: too small for sustained monitoring
- Authenticated REST/GraphQL with PAT: sufficient for NVP at effectively zero direct API cost
- Main cost: engineering discipline around rate limiting and storage

### Overall recommendation
**Best cost/stability tradeoff:**
- arXiv RSS + arXiv API + selective HTML/PDF fallback
- GitHub REST API with authenticated token

---

## 6. System Architecture

```text
[arXiv RSS discovery]
        ↓
[new paper queue]
        ↓
[arXiv API enrichment]
        ↓
[repo extraction pipeline]
   ├─ metadata/comment scan
   ├─ abstract HTML scan
   └─ PDF fallback scan
        ↓
[normalized paper + repo store]
        ↓
[GitHub repo polling jobs]
        ↓
[scoring + watchlist updates]
        ↓
[daily summary + JSON snapshot]
```

---

## 7. Proposed Project Structure

```text
arxiv-github-monitor/
  README.md
  docs/
    nvp-engineering-spec.md
  config/
    categories.yaml
    settings.yaml
  data/
    raw/
    processed/
    snapshots/
  src/
    ingest_arxiv_rss.py
    enrich_arxiv_api.py
    extract_repo_links.py
    normalize_entities.py
    poll_github_repos.py
    score_watchlist.py
    generate_daily_report.py
  state/
    papers.jsonl
    repos.jsonl
    repo_snapshots.jsonl
    checkpoints.json
  output/
    daily-report.md
    daily-report.json
  scripts/
    run_daily_pipeline.sh
    run_repo_poll.sh
```

---

## 8. Data Model

## 8.1 Paper record

```json
{
  "paper_id": "2505.12345",
  "version": "v1",
  "title": "Paper title",
  "authors": ["Author A", "Author B"],
  "summary": "Abstract text",
  "categories": ["cs.LG", "cs.AI"],
  "published_at": "2026-05-11T00:00:00Z",
  "updated_at": "2026-05-11T00:00:00Z",
  "abs_url": "https://arxiv.org/abs/2505.12345",
  "pdf_url": "https://arxiv.org/pdf/2505.12345",
  "source": "rss",
  "repo_candidates": ["https://github.com/org/repo"],
  "repo_extraction_status": "found",
  "repo_extraction_source": "abstract_html"
}
```

## 8.2 Repo master record

```json
{
  "repo": "org/repo",
  "paper_id": "2505.12345",
  "first_seen_at": "2026-05-11T08:00:00Z",
  "current_stars": 120,
  "current_forks": 15,
  "current_open_issues": 4,
  "current_watchers": 120,
  "language": "Python",
  "license": "MIT",
  "archived": false,
  "disabled": false,
  "default_branch": "main",
  "last_pushed_at": "2026-05-11T07:40:00Z",
  "tier": "A",
  "score": 0.78,
  "status": "active"
}
```

## 8.3 Repo snapshot record

```json
{
  "repo": "org/repo",
  "captured_at": "2026-05-11T12:00:00Z",
  "stars": 120,
  "forks": 15,
  "open_issues": 4,
  "watchers": 120,
  "last_pushed_at": "2026-05-11T07:40:00Z",
  "release_count": 1,
  "readme_hash": "abc123"
}
```

---

## 9. Extraction Logic

## 9.1 GitHub repo extraction order

For each new paper:

### Pass 1: metadata regex scan
Check all available text fields for:
- `github.com/<owner>/<repo>`
- shortened GitHub URLs if present

### Pass 2: abstract page HTML scan
Fetch `abs_url` and extract:
- direct GitHub anchors
- project page anchors that redirect to GitHub

### Pass 3: PDF fallback
Only trigger if:
- paper is category-relevant, and
- no repo found in earlier passes

PDF fallback can initially use text extraction plus regex; do not build a full PDF layout parser yet.

### Normalization rules
- strip trailing slashes
- remove fragment/query params
- canonicalize to lowercase `owner/repo` key where appropriate
- reject org/profile links with no repo slug

---

## 10. GitHub Polling Design

## 10.1 Polling tiers

### Tier A: newly discovered or fast-growing repos
**Criteria**
- first seen within 7 days, or
- significant recent star growth, or
- recent code push

**Frequency**
- every 6 hours

### Tier B: normal active watchlist
**Frequency**
- daily

### Tier C: low-signal long-tail repos
**Frequency**
- every 3 to 7 days

---

## 10.2 Core GitHub fields to fetch every poll
- stars
- forks
- watchers
- open issues
- pushed_at
- updated_at
- archived
- disabled
- description
- default branch
- language
- license

## 10.3 Extra fields for high-priority repos only
- recent commits
- release count / latest release
- contributors count
- README hash/content summary

---

## 11. Scoring Logic (NVP)

Use a simple heuristic score, not a learned model.

```text
Potential Score =
  0.30 * topic_match
+ 0.20 * repo_readiness
+ 0.20 * repo_activity
+ 0.15 * star_growth
+ 0.10 * docs_quality
+ 0.05 * release_or_demo_signal
```

### Example feature inputs
- `topic_match`: keyword/category match to user interests
- `repo_readiness`: presence of install steps, requirements, examples, license
- `repo_activity`: recent push and commit recency
- `star_growth`: delta over 24h / 7d
- `docs_quality`: README substance
- `release_or_demo_signal`: release, model weights, demo link, etc.

### Score bands
- `0.75+` = high potential
- `0.50–0.74` = worth watching
- `<0.50` = low signal / slow poll

---

## 12. Scheduling

## 12.1 Daily pipeline
Run once every morning:
1. fetch RSS feeds
2. detect unseen papers
3. enrich via API
4. extract repos
5. write new paper records
6. add new repos to watchlist
7. generate daily discovery report

## 12.2 Repo polling pipeline
Run separately:
- Tier A repos every 6 hours
- Tier B daily
- Tier C weekly

### Recommended separation
Keep `discovery` and `repo polling` as separate jobs so failures do not block each other.

---

## 13. Output Design

## 13.1 Daily markdown report

```markdown
# Daily arXiv → GitHub Report

## New papers with repos
- [2505.12345] Paper title
  - Categories: cs.LG, cs.AI
  - Repo: org/repo
  - Stars: 120
  - Last push: 2026-05-11
  - Why it matters: strong README + active updates

## High-potential repos
- org/repo — score 0.81
- org/another-repo — score 0.77

## Watchlist changes
- Upgraded to Tier A: org/repo
- Downgraded to Tier C: org/stale-repo
```

## 13.2 JSON output
Machine-readable payload for downstream automation:
- new papers
- new repos
- changed repo metrics
- top-ranked repos

---

## 14. Failure Handling

### arXiv failures
- If RSS fails, retry once and keep prior checkpoint.
- If API enrichment fails, store partial paper and retry later.
- If HTML/PDF extraction fails, mark extraction status and continue.

### GitHub failures
- If repo API returns 404, mark repo invalid or moved.
- If rate-limited, back off and requeue.
- If a repo becomes archived, demote polling frequency.

### Pipeline rule
Never let one bad paper or repo fail the whole daily run.

---

## 15. Implementation Roadmap

## Phase 0: NVP bootstrapping
- create folder structure
- add config files
- implement RSS discovery
- implement API enrichment
- implement basic GitHub URL extraction
- implement repo master store
- implement one daily markdown report

## Phase 1: useful monitoring
- add repo polling tiers
- add snapshots and deltas
- add simple scoring
- add keep/drop logic

## Phase 2: smarter filtering
- improve README scoring
- detect demos / checkpoints / installability
- add optional semantic topic matching

## Phase 3: downstream integration
- push report to Discord / Obsidian / dashboard
- persist weekly summaries
- add user-tunable topic weights

---

## 16. Concrete First Deliverables

### Deliverable A
`src/ingest_arxiv_rss.py`
- fetch category feeds
- return normalized paper stubs

### Deliverable B
`src/enrich_arxiv_api.py`
- fetch structured metadata for unseen papers
- merge into paper records

### Deliverable C
`src/extract_repo_links.py`
- run 3-pass extraction
- emit normalized repo candidates

### Deliverable D
`src/poll_github_repos.py`
- poll repo metadata via REST API
- write snapshots

### Deliverable E
`src/generate_daily_report.py`
- summarize new papers and repo changes
- write markdown + JSON

---

## 17. Minimal Success Criteria

The NVP is successful if within one run it can:
- discover new papers from selected arXiv categories,
- identify at least some papers with valid GitHub repos,
- normalize repos into a stable watchlist,
- poll those repos on a schedule,
- output a readable daily report.

---

## 18. Open Questions

1. Which categories should be in or out at launch?
2. Should project-page URLs that later redirect to GitHub be preserved alongside repo URLs?
3. What output destination should be primary after local file generation: Discord, Obsidian, or both?
4. Should star-growth ranking be absolute or topic-weighted?

---

## 19. Recommendation

Start with the narrowest robust pipeline:

- **Discovery:** arXiv RSS
- **Enrichment:** arXiv API
- **Repo extraction:** metadata → abstract page → PDF fallback
- **Monitoring:** GitHub REST API with PAT
- **Storage:** local JSONL files first
- **Output:** markdown report + JSON snapshot

This yields the best early tradeoff between stability, engineering effort, and cost.
