# NxtBuild

Describe a website in plain words and NxtBuild builds it with Gemini. You get a live preview,
a chat to keep changing the page, a code editor, and a one-click download.

**Stack:** React 19 + Vite, React Router, Context API, axios | FastAPI (Python), Motor (MongoDB), PyJWT, Google GenAI (`google-genai`)

---

## 4-Service Microservices Architecture

NxtBuild is architected into 4 decoupled, independently scalable microservices:

```
                      +-----------------------------+
                      |   React 19 Frontend (Vite)  |
                      |    http://localhost:5173    |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |     API Gateway (5050)      |
                      |  Routing, CORS, Aggregation |
                      +----+---------+---------+----+
                           |         |         |
         +-----------------+         |         +-----------------+
         |                           |                           |
         v                           v                           v
+------------------+       +------------------+       +------------------+
|   Auth Service   |       |  Project Service |       |    AI Service    |
|   (Port 8001)    |       |   (Port 8002)    |       |   (Port 8003)    |
| Users, JWT, Hash |       | CRUD, Code, Chat |       | Gemini 2.5 Flash |
+--------+---------+       +--------+---------+       +--------+---------+
         |                          |                          |
         |                          +------------<-------------+ (Code sync)
         |                          |
         v                          v
+---------------------------------------------+
|            MongoDB Atlas Database           |
+---------------------------------------------+
```

### The 4 Microservices

1. **API Gateway (`server/gateway`, Port `5050`):**
   - Single public entry point for all frontend requests (`/api/auth/*`, `/api/projects/*`, `/api/health`).
   - Reverse-proxies traffic asynchronously to the corresponding internal services.
   - Handles CORS and aggregates cluster health check (`/api/health`).

2. **Auth Service (`server/services/auth`, Port `8001`):**
   - User registration, password hashing (`bcrypt`), and JWT generation/verification (`pyjwt`).
   - Provides internal verification endpoint (`/auth/verify`) for zero-trust service-to-service validation.

3. **Project Service (`server/services/projects`, Port `8002`):**
   - Project CRUD operations, chat message history, and HTML code persistence.
   - Provides internal secure endpoint (`PUT /internal/projects/:id/generated-code`) for the AI service.

4. **AI Generation Service (`server/services/ai`, Port `8003`):**
   - Prompt engineering and orchestrating Google Gemini 2.5 Flash (`v1beta` HTTP options).
   - Enforces per-project concurrency locking (`asyncio.Lock`) to prevent race conditions during rapid prompts.
   - Automatically commits generated HTML and assistant explanations back to Project Service.

---

## Running NxtBuild

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB URI (local or Atlas)
- Google Gemini API key from https://aistudio.google.com

### Option A: Local Development (Multi-Service Runner)

1. **Setup Backend:**
   ```bash
   cd server
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env    # Fill in MONGODB_URI, JWT_SECRET, and GEMINI_API_KEY
   ```

2. **Start All 4 Microservices:**
   ```bash
   python run_services.py
   ```
   *This launches Auth (8001), Projects (8002), AI (8003), and the Gateway (5050) concurrently with graceful shutdown.*

3. **Start Frontend:**
   ```bash
   cd client
   npm install
   npm run dev
   ```
   Open http://localhost:5173

---

### Option B: Docker Compose

Run the entire backend cluster in isolated Docker containers:

```bash
cd server
docker-compose up --build
```

- Gateway exposed on port `5050`
- Services communicate over an internal Docker bridge network (`nxtbuild-net`)

---

### Option C: Monolithic Fallback

If you prefer to run the single-process monolith:
```bash
cd server
uvicorn main:app --reload --port 5050
```

---

## Deployment on Render

NxtBuild includes a ready-to-use Render Blueprint (`server/render.yaml`):

1. Push your repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com), click **New +** $\rightarrow$ **Blueprint**.
3. Select this repository. Render reads `server/render.yaml` and provisions:
   - **`nxtbuild-gateway`** (Public Web Service)
   - **`nxtbuild-auth-service`** (Private Service)
   - **`nxtbuild-project-service`** (Private Service)
   - **`nxtbuild-ai-service`** (Private Service)
4. Enter your environment variables (`MONGODB_URI`, `JWT_SECRET`, `GEMINI_API_KEY`) when prompted.
5. Deploy the frontend on **Vercel** or **Render Static Site**, pointing `VITE_API_URL` to your Render Gateway URL.

---

## API Endpoints

All external client requests hit the **API Gateway** on port `5050`:

| Method | Route | Service Routed To | Description |
| --- | --- | --- | --- |
| GET | `/api/health` | Gateway (Aggregated) | Health status of all 4 services |
| POST | `/api/auth/signup` | Auth Service (8001) | Create new user account |
| POST | `/api/auth/login` | Auth Service (8001) | Authenticate user, return JWT |
| GET | `/api/auth/me` | Auth Service (8001) | Fetch authenticated user profile |
| GET | `/api/projects` | Project Service (8002) | List all projects for authenticated user |
| POST | `/api/projects` | Project Service (8002) | Create a new project |
| GET | `/api/projects/:id` | Project Service (8002) | Fetch project details, code & chat history |
| PUT | `/api/projects/:id` | Project Service (8002) | Update project title or manual code edits |
| DELETE | `/api/projects/:id` | Project Service (8002) | Delete a project |
| POST | `/api/projects/:id/generate` | AI Service (8003) | Generate/update page using Gemini AI |

---

## Folder Map

```
server/
  gateway/               # API Gateway (Reverse proxy, CORS, Health aggregation)
    main.py
    config.py
    Dockerfile
  services/
    auth/                # Auth Service (JWT, Bcrypt, Verification)
      main.py
      security.py
      database.py
      config.py
      Dockerfile
    projects/            # Project Service (CRUD, MongoDB, History)
      main.py
      database.py
      serializers.py
      deps.py
      config.py
      Dockerfile
    ai/                  # AI Service (Gemini 2.5 Flash, Concurrency lock)
      main.py
      gemini.py
      concurrency.py
      deps.py
      config.py
      Dockerfile
  docker-compose.yml     # Multi-container orchestration
  render.yaml            # Render Blueprint deployment
  run_services.py        # Local multi-process runner
  test_microservices_e2e.py  # End-to-end integration test suite
client/src/
  pages/                 # Landing, Login, Dashboard, Builder
  components/            # Navbar, ProjectCard, ChatPanel, PreviewPanel, HeroDemo
  context/               # AuthContext
  api/                   # Axios client instance
  styles/                # Modular CSS styling
```

---

## Security & Sandboxing

- Generated pages run inside a sandboxed `<iframe>` (`sandbox="allow-scripts allow-modals allow-forms"` and **without** `allow-same-origin`), ensuring AI-generated scripts can never access host cookies, session storage, or the backend API.
- All internal microservices validate requests via zero-trust internal endpoints or private networking.
- Prompts are validated with a 2,000-character cap and per-project concurrency locks prevent overlapping generation calls.
