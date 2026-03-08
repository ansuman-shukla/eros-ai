# Eros AI

Welcome to **Eros AI**! This is an open-source, deeply personal AI companion platform featuring persistent memory, an evolving personality engine, real-time emotional intelligence, and native voice and chat interaction capabilities.

Unlike generic chatbots, Eros AI is designed to maintain a long-term, evolving understanding of the user. It remembers your history, observes your habits, and incrementally builds a Carl Jung-inspired psychological profile of you over time. Interaction is seamless across **text chat** and **live voice calls**, both sharing the same underlying memory, personality, and session infrastructure.

---

## 🚀 Features

*   **Persistent Memory System:** Hot memory (core facts) and Cold memory (episodic context) architecture.
*   **Personality Engine:** Carl Jung-inspired psychological profiling incrementally updated via trait deltas.
*   **Emotional Awareness:** Prompt-native mood inference for real-time adaptation of tone and behavior.
*   **Native Voice Pipeline:** LiveKit WebRTC integration with near-instant responses using filler-bridged memory retrieval.
*   **Background Pipelines:** Async worker jobs for memory curation, personality updates, and automated diary writing.
*   **Gamification:** Coin-based engagement system to unlock companion features.

---

## 🛠 Tech Stack

*   **Backend:** FastAPI (Python 3.12)
*   **Frontend:** Next.js (React, TypeScript)
*   **Database:** MongoDB (Beanie ODM)
*   **Caching & Queue:** Redis for fast memory lookup and ARQ for background jobs.
*   **Voice Integration:** LiveKit (WebRTC), Deepgram (STT/TTS), Cerebras (LLM).
*   **Intelligence:** Gemini SDK (for memory retrieval, curation, and personality pipelines).

---

## 🏗 Architecture Overview

The platform uses a unified **Shared Session Core** for both chat and voice interactions:

1.  **Session Initialization:** Pulls Hot and Cold memory from MongoDB into Redis.
2.  **During Session:** Purely Redis-backed operations. The LLM emits a decision token (`SEARCH` or `NO_SEARCH`) to determine if a sub-500ms Gemini memory retrieval step is needed before responding.
3.  **Session Teardown:** Redis states are flushed to MongoDB and async background jobs (curation, personality updates, diary generation) are enqueued via ARQ.

For a deeper dive, check out the [Platform & Code Architecture](./platform-architecture.md) and the [Product Requirements Document (PRD)](./eros-prd.md).

---

## 💻 Getting Started (Local Development)

To run Eros AI locally, you'll need Docker installed.

### Prerequisites

*   Python 3.12+
*   Node.js 20+
*   Docker & Docker Compose
*   Required API Keys: Gemini, LiveKit, Deepgram, Cerebras

### Setting up the Environment

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ansuman-shukla/eros-ai.git
    cd eros-ai
    ```

2.  **Configure environment variables:**
    Copy the `.env.example` in the `backend/` directory to `.env` and fill in your API keys.
    ```bash
    cp backend/.env.example backend/.env
    ```

### Running the Services

The easiest way to get the infrastructure (MongoDB, Redis) running is via Docker Compose:

```bash
docker-compose up -d
```

#### 1. Start the FastAPI Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### 2. Start the Background ARQ Worker
In a new terminal:
```bash
cd backend
source venv/bin/activate
python scripts/run_worker.py
```

#### 3. Start the Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```

#### 4. (Optional) Start the LiveKit Voice Agent
To enable voice capabilities:
```bash
cd voice-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python agent.py start
```

---

## 🧪 Running Tests

The project follows a strict Test-Driven Development (TDD) approach. We use `pytest` with a dedicated MongoDB test database.

```bash
cd backend
source venv/bin/activate
pytest tests/
```

To run specific test suites:
```bash
pytest tests/unit/
pytest tests/integration/
```

---

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1.  **Read the Documentation:** Familiarize yourself with the [Implementation Plan](./implementation-plan.md) and [Architecture](./platform-architecture.md). We build backend-first and ensure comprehensive test coverage before touching the UI.
2.  **Test-Driven Development (TDD):** The core principle of this project is Red → Green → Refactor. Ensure your feature is fully covered by unit and integration tests *before* submitting a PR.
3.  **Mock External APIs:** Do not make real calls to Gemini, Cerebras, or Deepgram in unit tests. Use mocks.
4.  **Create a Branch:** `git checkout -b feature/your-feature-name`
5.  **Commit and Push:** Write clear, descriptive commit messages. Provide a detailed PR description.

---

## 📜 License

[Add License Information Here]
