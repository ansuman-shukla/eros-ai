# Companion AI

> A deeply personal AI companion with persistent memory, evolving personality modeling, real-time emotional intelligence, and native voice + chat interaction.

## Overview

Unlike generic chatbots, **Companion AI** is designed to maintain a long-term, evolving understanding of the user. It remembers your history, observes your habits, and incrementally builds a Carl Jung-inspired psychological profile of you over time. Interaction is seamless across **text chat** and **live voice calls**, both of which share the same underlying memory, personality, and session infrastructure.

## Key Features

*   **Persistent Memory System:**
    *   **Hot Memory:** Core, high-frequency facts (name, age, key relationships) kept in Redis and always present in the system prompt.
    *   **Cold Memory:** Episodic and contextual memories queried on demand using a Gemini-powered retrieval pipeline and cached in Redis.
*   **Personality Engine (Trait Delta System):**
    *   The companion builds a psychological profile based on Carl Jung's analytical psychology (Introversion/Extroversion, Sensing/Intuition, Thinking/Feeling).
    *   Traits are updated incrementally after every session based on behavioral evidence (Trait Deltas).
*   **Emotional Awareness:**
    *   Uses **Prompt-Native Inference** to read emotional signals from the conversation dynamically and respond proportionally with appropriate tone, pacing, and warmth.
*   **Native Voice Integration:**
    *   Powered by LiveKit, Deepgram, and Cerebras.
    *   Near-instant voice responses using a novel **Filler-Bridged Search** strategy: the agent speaks a natural filler phrase ("Let me think about that...") while querying memory in the background.
*   **Automated Background Pipelines:**
    *   Operates asynchronously after sessions end via ARQ workers.
    *   **Memory Curation:** Extracts and reconciles new memories.
    *   **Personality Update:** Computes trait deltas and evolves the user profile.
    *   **Diary Writer:** Generates a daily, first-person reflective diary entry written *by* the companion *about* the user.
*   **Gamification:**
    *   A coin ledger system rewards users for interaction, allowing them to unlock features like the companion's hidden diary entries.

## Tech Stack & Infrastructure

*   **Backend:** FastAPI (Python 3.12)
*   **Frontend:** Next.js (React, TypeScript)
*   **Database:** MongoDB (using Beanie ODM)
*   **Cache & Session State:** Redis + ARQ (Background job queue)
*   **Voice Pipeline:** LiveKit, Deepgram (STT/TTS), Cerebras (Fast LLM integration)
*   **Intelligence & Ops:** Gemini SDK (Cold Memory Retrieval, Curation, Personality Updates, Diary Generation)

## Architecture

The platform architecture distinctly separates the I/O layer (Chat vs. Voice) from a highly optimized **Shared Session Core**. 

1.  **Session Init:** All Hot and Cold memory is pulled from MongoDB entirely into Redis.
2.  **During Session:** Zero database round-trips. A single "Decision Token" (SEARCH or NO_SEARCH) dictates if the agent responds directly or runs a sub-500ms Gemini retrieval step against Redis memory keys.
3.  **Session End:** Redis states are flushed to MongoDB and async background jobs (curation, personality evolvement) are enqueued. 

Refer to [`platform-architecture.md`](./platform-architecture.md) for detailed service maps and schemas.

## Implementation Roadmap

Development follows a strict Test-Driven Development (TDD) approach outlined in [`implementation-plan.md`](./implementation-plan.md), structured into 6 main phases:

*   **Phase 0:** Project Scaffolding & Infrastructure (FastAPI, Mongo, Redis, ARQ)
*   **Phase 1:** Auth + User Foundation (JWT, Registration)
*   **Phase 2:** Memory System + Session Lifecycle (Redis caching, Hot/Cold memory CRUD)
*   **Phase 3:** Core Chat Pipeline (WebSockets, Decision Engine, Gemini Retrieval)
*   **Phase 4:** Background Pipelines (ARQ tasks: Curation, Personality, Diary, Coins)
*   **Phase 5:** Voice Pipeline (LiveKit Agent, Filler-Bridged Search, Deepgram integration)
*   **Phase 6:** Dashboard API + Next.js Frontend

## Documentation

For a comprehensive dive into the product reasoning and architectural details, please review:
*   [Product Requirements & Architecture (PRD)](./eros-prd.md)
*   [Platform & Code Architecture](./platform-architecture.md)
*   [Implementation Plan & Testing Strategy](./implementation-plan.md)
