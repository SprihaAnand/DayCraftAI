# DayCraft

DayCraft is an AI-first daily planner for people who want a usable day, not another pile of tasks. It combines a private task inbox, reviewable natural-language capture, protected calendar commitments, an AI-written agenda, a secondary visual time canvas, and a focused work timer.

The product flow is intentionally small:

**Capture → choose a day pace → protect time → craft a written AI agenda → see it on the clock → focus → review.**

The interface is an original schedule-studio implementation informed by the real calendar canvas of [Morgen Schedule Builder](https://www.morgen.so/schedule-builder), the focused action hierarchy of [Calendly](https://calendly.com/), the contextual schedule-side-panel pattern seen in [Dribbble's scheduling explorations](https://dribbble.com/search/schedule-management-dashboard), and a restrained touch of the visual energy in [Spriha's portfolio](https://sprihaanand.github.io/MyPortfolio/). It does not copy their assets or interface.

## What works

- Email-and-password accounts with salted PBKDF2 password hashes.
- Durable, user-scoped SQLite data. Sign back in with the same email and password to find your tasks, plans, focus sessions, and check-ins.
- A review-first **Drop in your day** capture flow. Type a loose list such as `Lunch from 1 to 2, workout, meeting at 9 for half an hour, read 10 pages`; an explicit time range or a start plus duration becomes a protected commitment, while the remaining items stay flexible tasks. Nothing is stored until the user reviews and confirms it.
- Three intentional day paces — **Chill**, **Balanced**, and **Work-heavy**. They set the deterministic template, capacity, and transition room so a person can say how full the day should feel without manually designing a calendar.
- Gemini or OpenAI planning. An AI provider is required to craft a daily plan; DayCraft never silently substitutes a local heuristic for an AI-generated plan.
- Session-only AI keys entered in the browser, plus deployment-owned environment keys. Browser keys are never written to SQLite, exported, or placed in URLs, and they are cleared on sign-out.
- An **AI-written day plan first**: Gemini or OpenAI chooses an order and gives concise, time-free task cues. DayCraft then builds the written agenda from locally validated times and protected commitments. The calendar canvas is a secondary mirror of that agenda, not the primary answer or a source of AI-created times.
- Local schedule validation: AI can reference only task IDs from the submitted task list. DayCraft itself assigns time slots, preserves fixed commitments, and rejects model guidance that attempts to add times or move calendar reality.
- A session-only **Ask DayCraft about today** coach beneath the plan. It uses the already configured AI provider, reads only a bounded selected-day summary, and cannot create, move, save, send, or otherwise change anything.
- A local Model Context Protocol (MCP) server with user-scoped task and protected-commitment tools. It works only with the selected DayCraft workspace and does not send data to external services.
- Focus sessions and Review are real features, not placeholder pages: Focus records durable minutes; Review turns real completion/focus/check-in data into trends.

## Project layout

```text
DayCraftAI/
├── .streamlit/
│   └── config.toml             # root-level Cloud theme configuration
├── README.md
└── ai-productivity-assistant/
    ├── app.py                  # Streamlit entry point
    ├── app_pages/              # Today, Tasks, Focus, Review, Settings routes
    ├── components/             # auth, theme, session-only AI setup, workspace helpers
    ├── pages/                  # product workflows and page renderers
    ├── services/               # SQLite, auth, planning, AI, and compatibility services
    ├── mcp_server.py           # local stdio MCP server
    ├── tests/                  # mocked integration, security, and UI smoke tests
    ├── .env.example            # safe local configuration template
    ├── .streamlit/
    │   └── secrets.toml.example # safe Cloud secrets template (never commit secrets.toml)
    └── requirements*.txt
```

## Run locally

DayCraft supports Python 3.11+. Python 3.12 is a good Windows default.

```powershell
cd C:\Users\Spriha\Desktop\DayCraftAI
py -3.12 -m venv ai-productivity-assistant\.venv
.\ai-productivity-assistant\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r ai-productivity-assistant\requirements-dev.txt
Copy-Item ai-productivity-assistant\.env.example ai-productivity-assistant\.env
streamlit run ai-productivity-assistant\app.py
```

Open the URL Streamlit prints (normally `http://localhost:8501`). Create an account, use **Tasks → Drop in your day** to capture work in plain language, review the proposed tasks and commitments, then open **Today**. Choose **Chill**, **Balanced**, or **Work-heavy**, protect any remaining commitments, and select **Create my written plan**. Read the agenda first; the time canvas beneath it is the secondary clock view. The default local database is `ai-productivity-assistant/data/daycraft.db`; keep that directory on persistent storage if you want data to survive redeployments.

### Refreshing and restarting locally

Saved Python/UI changes normally hot-reload; refresh the browser if the page does not rerun on its own. A full local restart is safest after changing `.env`, dependencies, the Python version, or `.streamlit/config.toml`: press `Ctrl+C` in the terminal, then run `streamlit run ai-productivity-assistant\app.py` again. An app restart clears browser-only session state, so you may need to sign in again and re-enter a session-only AI key.

## Deploy a public Streamlit URL

This repository is prepared for [Streamlit Community Cloud](https://share.streamlit.io/). It uses the repository root for the Cloud configuration, while the app and its `requirements.txt` stay together in `ai-productivity-assistant/`.

1. Commit and push the project to GitHub. Do **not** commit `.env`, a database, or any `secrets.toml` file.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/), connect GitHub, and choose **Create app**.
3. Select repository `SprihaAnand/DayCraftAI`, branch `main`, and entry point `ai-productivity-assistant/app.py`.
4. Choose a memorable subdomain. This deployment uses `daycraftai`, so its public URL is `https://daycraftai.streamlit.app`.
5. In **Advanced settings**, choose Python 3.12 and paste root-level TOML secrets. Start from [`secrets.toml.example`](ai-productivity-assistant/.streamlit/secrets.toml.example), replacing every placeholder. Do not put these values under a TOML section: DayCraft reads them as environment variables.
6. Deploy, then set the app's sharing setting to public if Community Cloud does not already make it public.

### When a GitHub change becomes visible

After you push a commit to the repository and branch selected in Community Cloud, Cloud should detect it and build a new deployment automatically. Check the deployment log for that commit; a manual reboot is not normally required. Use **Reboot app** only after the new deployment finishes if the running process is stuck or a just-updated Cloud secret has not been picked up. A reboot cannot deploy code that has not been pushed.

If Cloud still serves an old or inaccessible app after a successful push, verify its repository, branch, and entry point, then use the recovery steps below. In particular, an old deployment created with the wrong Python runtime should be recreated with Python 3.12 rather than repeatedly rebooted.

For a Gemini-backed public preview, the secret block should look like this (with newly generated, private values):

```toml
DAYCRAFT_AI_PROVIDER = "gemini"
GEMINI_API_KEY = "replace-with-your-gemini-key"
GEMINI_MODEL = "gemini-3.8-flash"
DAYCRAFT_TIMEZONE = "Asia/Kolkata"
```

Export any useful data before deleting a running Cloud app. Community Cloud local files, including this project’s SQLite database, are not a durable production data store.

### Important: public preview vs. production

Community Cloud is a good way to share an AI-planning preview, but it is not a production data store for this app. Its local files are not guaranteed to persist, whereas DayCraft currently stores accounts and planning data in SQLite. Do not advertise durable public accounts until the data layer is moved to a managed database.

## Configure the required AI planner

DayCraft needs either Gemini or OpenAI before it can craft a daily plan. There are two safe choices.

### Option A — enter a key for the active browser session

After signing in, open **Today** or **Settings → AI planner**, choose **Gemini** or **OpenAI**, and paste a key. The key is held in Streamlit session memory only; it is not saved to the DayCraft database and is cleared when you sign out. This is useful for a personal/self-hosted instance where each person brings their own key.

### Option B — configure a deployment key

Put one provider’s values in `ai-productivity-assistant/.env` for local development, or set them in the deployment’s secret manager for production:

```dotenv
# Choose Gemini (default) or OpenAI when both keys are available.
DAYCRAFT_AI_PROVIDER=gemini

GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.8-flash

# Or use OpenAI instead.
# DAYCRAFT_AI_PROVIDER=openai
# OPENAI_API_KEY=your_openai_key
# OPENAI_MODEL=gpt-5.2
```

Do not hardcode a key in Python or commit `.env`. Gemini calls use the maintained `google-genai` Interactions API and OpenAI calls use the Responses API. Both are one-shot requests with provider-side storage disabled (`store=False`). For a day plan, AI receives only task planning fields and fixed-commitment timing, returns a constrained ordering, and cannot create or move calendar events by itself. See the official [OpenAI Responses API reference](https://platform.openai.com/docs/api-reference/responses) and [Google Gen AI SDK documentation](https://ai.google.dev/gemini-api/docs/libraries).

If a provider key is absent or the provider returns unusable planning output, DayCraft refuses to save a non-AI day plan and explains the problem. For a valid request, the provider creates the theme, priority order, and short task cues; DayCraft creates the exact, validated written agenda and calendar blocks locally. Lightweight Focus/Review coaching may show a local fallback because it cannot change your schedule.

## Use the MCP server

The optional local MCP server lets a compatible AI client work with one DayCraft account over stdio. It is separate from the Streamlit website and takes the target identity from the process environment—not from tool parameters—so an LLM cannot switch accounts with a prompt.

```powershell
cd C:\Users\Spriha\Desktop\DayCraftAI\ai-productivity-assistant
$env:DAYCRAFT_MCP_USER_EMAIL = "you@example.com"
.\.venv\Scripts\python.exe mcp_server.py
```

Configure your MCP client to run the same command from this directory with the same environment. The server is scoped to the account identified by `DAYCRAFT_MCP_USER_EMAIL`; tool parameters cannot switch to another account.

Available tools include:

- `get_today_brief`, `list_open_tasks`, `create_task`, `complete_task`, and `list_agenda`.
- `create_daycraft_event` to create a local protected commitment.

See the [official MCP Python SDK documentation](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/index.md) for client configuration examples.

## How the product works

1. **Capture** — In **Tasks**, use **Drop in your day** for a natural list or add one precise task manually. The parser is deterministic and bounded: only an explicit same-day range or a start plus duration is proposed as protected time. Review every item before it is saved.
2. **Choose a pace** — In **Today**, select **Chill**, **Balanced**, or **Work-heavy**. The pace controls a local template, task capacity, and transition buffer while retaining essential breaks and a closeout.
3. **Protect time** — Add fixed commitments in **Today** or accept reviewed commitments from quick capture. These always win and can never be moved by AI.
4. **Craft the written agenda** — Gemini or OpenAI prioritizes only actual task IDs and supplies brief task cues. DayCraft’s local scheduler fits that order only inside verified template windows and around protected commitments, then presents the resulting text agenda first.
5. **See the clock** — The vertical time canvas below the agenda mirrors those validated blocks. It is useful for scanning the day, but it does not replace the written plan.
6. **Ask safely** — Use **Ask DayCraft about today** for a short explanation or next-step suggestion. Its chat history stays in the browser session; it cannot modify tasks, protected time, or anything external.
7. **Act** — Start a task-linked Focus timer from the plan. Completed minutes are persisted.
8. **Review** — Add a short check-in and view trends based only on activity the user recorded.

## Verify the project

Run these commands from `ai-productivity-assistant`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q -x "venv|__pycache__" .
.\.venv\Scripts\python.exe -m ruff check .
```

The test suite uses mocked AI-provider requests, so it never consumes an API key. It covers account isolation, durable data, session-key UI flow, AI provider contracts and safety filtering, MCP user scoping, natural-language capture review rules, paced planner capacity, ordinary planner gap placement, built-in schedule templates, and all primary Streamlit routes.

## Deployment and security notes

- Do not commit `.env`, `data/daycraft.db`, deployment secrets, or virtual environments.
- Community Cloud does not guarantee persistence for local files. It can publish a useful preview, but the current SQLite backend is not sufficient for a public, durable multi-user deployment.
- Rotate any API key that may have appeared in a previous Git commit. If the repository was shared, use your organization’s approved history-cleanup process.
- SQLite is appropriate for a personal/self-hosted persistent volume. Before a public multi-user launch, use HTTPS, a managed relational database, a managed identity/OIDC provider with email verification and password reset, rate limiting, backups, centralized secrets, and logging.
