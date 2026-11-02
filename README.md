# 🔥 Ember — HackAiThon

Tell Ember a **goal** (chess rating, pilot's license, CDL…) or an **activity** (go-karts, paintball,
off-roading, hunting…). Ember reads its **soul**, recalls what it **remembers about you**, **searches the
web**, and brings back 2–3 genuinely different **plans**. Pick one and Ember builds the deliverable:
a gamified **quest line** (levels, quests, XP, boss fights, achievements) for goals, or a full
**outing plan** (venues, itinerary, budget, checklist, safety, side quests) for activities.

**Stack:** Python · FastAPI · SQLite · React (Vite) · Claude API with server-side web search

## Run it

```bash
# 1. backend  (terminal 1)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your ANTHROPIC_API_KEY in .env
uvicorn main:app --reload --port 8000

# 2. frontend (terminal 2)
cd frontend
npm install
npm run dev                   # http://localhost:5173  (proxies /api -> :8000)
```

No API key? The app still runs in **demo mode** with offline template plans (a banner tells you).

Single-server mode: `cd frontend && npm run build`, then just run the backend; it serves `frontend/dist`.

## How the AI works

```
request ──► read soul.md ──► recall memory (SQLite, relevance + recency)
        ──► web research (Claude + web_search tool, cited sources)
        ──► craft 3 plans (JSON)  ──► user chooses
        ──► build artifact (quest board / outing plan) ──► progress + XP tracked
```

| Piece | Where |
|---|---|
| **Soul** — who Ember is (identity, voice, values, rules). Loaded into every call. Edit it! | `backend/soul.md` |
| **Memory** — profile + memory notes. Top matches go into every prompt. Ember writes memories when you choose a plan or clear a level; you can add/delete them on the *Me & Memory* page. | `backend/db.py` (`memories`) |
| **RAG / research** — live web search, sources attached to plans | `backend/ai.py` (`research_web`) |
| **Plans & artifacts** — JSON-schema prompts, validation, XP maps | `backend/ai.py` |
| **Pipeline & API** — background tasks, status polling | `backend/main.py` |

Config: `CLAUDE_MODEL` (default `claude-sonnet-5-5`) and `ANTHROPIC_API_KEY` in `backend/.env`.
If a live call fails, the request degrades to offline templates and says so on screen.

## API

`GET /api/health · /stats · /soul` · `GET/PUT /api/profile` · `GET/POST/DELETE /api/memories`
`POST /api/requests {kind: "goal"|"activity", params}` → poll `GET /api/requests/{id}`
`POST /api/plans/{id}/choose` → poll `GET /api/artifacts/{id}` · `PUT /api/artifacts/{id}/progress`
