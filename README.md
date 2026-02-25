# Customer Support AI Agent

Customers can create support tickets and receive AI-generated responses.

## Features

- **Create a ticket**: Submit subject, description, and email.
- **AI response**: Each ticket gets an immediate reply from an LLM via [OpenRouter](https://openrouter.ai).
- **Web UI**: Simple support portal to submit tickets and view the AI reply.
- **API**: REST endpoints for integration.

## Setup

1. **Create a virtual environment** (recommended):

   ```bash
   cd customer_support_ai
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure OpenRouter**:

   Copy `.env.example` to `.env` and set your OpenRouter API key:

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # macOS/Linux
   ```

   Edit `.env` and set `OPENROUTER_API_KEY`. Get a key at [openrouter.ai/keys](https://openrouter.ai/keys).

4. **Optional – Supabase (persistent storage)**:

   Without Supabase, users, sessions, tickets and chat channels are stored in memory and lost on restart. To persist data:

   - Create a free project at [supabase.com](https://supabase.com).
   - In the Supabase dashboard, open **SQL Editor** and run the script in `supabase/schema.sql` to create the tables.
   - In **Project Settings → API**, copy the **Project URL** and the **anon public** key.
   - In your `.env`, set:
     ```bash
     SUPABASE_URL=https://xxxxx.supabase.co
     SUPABASE_KEY=your-anon-key
     ```
   - Restart the app. It will use Supabase for users, sessions, tickets, and channels.

## Run

From the project root (`customer_support_ai`):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Web UI**: Open [http://localhost:8000](http://localhost:8000)
- **API docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

## API

| Method | Endpoint        | Description                          |
|--------|-----------------|--------------------------------------|
| GET    | `/`             | Support portal (HTML)                |
| POST   | `/tickets`      | Create a ticket and get AI response  |
| GET    | `/tickets/{id}` | Get a ticket and its AI response     |
| GET    | `/tickets`      | List all tickets                     |

### Create ticket (POST /tickets)

```json
{
  "customer_email": "customer@example.com",
  "subject": "Login not working",
  "description": "I cannot log in with my password since this morning."
}
```

Response includes `ticket_id`, `ai_response`, `status`, etc.

## Project structure

```
customer_support_ai/
├── app/
│   ├── __init__.py
│   ├── config.py       # env / LLM settings
│   ├── main.py         # FastAPI app and routes
│   ├── models.py       # Pydantic models
│   ├── ticket_store.py # In-memory ticket storage
│   ├── llm_agent.py    # OpenRouter-based support agent
│   └── templates/
│       └── index.html  # Support portal UI
├── requirements.txt
├── .env.example
└── README.md
```

If `SUPABASE_URL` and `SUPABASE_KEY` are set, the app uses Supabase for users, sessions, tickets, and channels. Otherwise, data is stored in memory and is lost on restart.

## Deploy (where and how)

The app is a **FastAPI** app run with **Uvicorn**. You can deploy it to any host that runs Python and supports env vars. Good options:

| Where | Best for | Notes |
|-------|----------|--------|
| **[Railway](https://railway.app)** | Easiest, free tier | Connect repo → set env vars → deploy. Auto-detects Python and runs `uvicorn`. |
| **[Render](https://render.com)** | Free tier, simple | New Web Service → connect repo → build: `pip install -r requirements.txt`, start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. |
| **[Fly.io](https://fly.io)** | Global regions, free tier | Use a `Dockerfile` or `fly.toml`; good if you want containers. |
| **Google Cloud Run** | Scale-to-zero | Package in a container, set env vars in the console. |
| **AWS (ECS / Elastic Beanstalk)** | Full control | More setup; use a Dockerfile or Elastic Beanstalk Python platform. |

### Deploy on Railway (quick path)

1. Push your code to **GitHub** (see “Pushing to GitHub” below).
2. Go to [railway.app](https://railway.app) and sign in (e.g. with GitHub).
3. **New Project** → **Deploy from GitHub repo** → select your repo.
4. In the new service, open **Variables** and add:
   - `OPENROUTER_API_KEY` = your OpenRouter API key  
   - Optionally: `SUPABASE_URL`, `SUPABASE_KEY` (and any other vars from `.env`).
5. In **Settings** → **Deploy**:
   - **Build command**: leave default or `pip install -r requirements.txt`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Root directory**: project root (where `app/` and `requirements.txt` are).
6. Deploy. Railway will assign a URL like `https://your-app.up.railway.app`.

### Deploy on Render

1. Push your code to **GitHub**.
2. Go to [render.com](https://render.com) → **New** → **Web Service**.
3. Connect your GitHub repo and choose the repo/branch.
4. Configure:
   - **Environment**: Python 3
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Root directory**: leave blank if the repo root is the project root.
5. **Environment** tab: add `OPENROUTER_API_KEY`, and optionally `SUPABASE_URL`, `SUPABASE_KEY`.
6. **Create Web Service**. Your app will be at `https://your-service.onrender.com`.

### What to set in production

- **Required**: `OPENROUTER_API_KEY` (from [openrouter.ai/keys](https://openrouter.ai/keys)).
- **Recommended**: `SUPABASE_URL` and `SUPABASE_KEY` so tickets, users, and chat are persisted.
- Do **not** commit `.env`; use each platform’s “Environment variables” or “Secrets” UI.

## Pushing to GitHub

1. **Create a new repository on GitHub**
   - Go to [github.com/new](https://github.com/new).
   - Choose a name (e.g. `customer_support_ai`), leave it empty (no README/license), then **Create repository**.

2. **Push this project** (from the project root):

   ```bash
   git add .
   git commit -m "Initial commit: Customer Support AI with tickets, chat, login and dashboard"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and the repo name you chose.
