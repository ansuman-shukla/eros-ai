const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { getToken } from "./auth";

interface FetchOptions extends RequestInit {
    skipAuth?: boolean;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
    const { skipAuth, ...fetchOptions } = options;
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(fetchOptions.headers as Record<string, string>),
    };

    if (!skipAuth) {
        const token = getToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
    }

    const res = await fetch(`${API_BASE}${path}`, {
        ...fetchOptions,
        headers,
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API error: ${res.status}`);
    }

    return res.json();
}

// ─── Auth ────────────────────────────────────────────────────

export interface LoginResponse {
    user_id: string;
    token: string;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
    return apiFetch("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
        skipAuth: true,
    });
}

export async function register(email: string, password: string, name: string): Promise<LoginResponse> {
    return apiFetch("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, name }),
        skipAuth: true,
    });
}

export interface UserProfile {
    id: string;
    email: string;
    name: string;
    language: string;
}

export async function getMe(): Promise<UserProfile> {
    return apiFetch("/api/v1/auth/me");
}

// ─── Session ─────────────────────────────────────────────────

export interface SessionInit {
    session_id: string;
}

export async function initSession(mode: string = "chat"): Promise<SessionInit> {
    return apiFetch("/api/v1/session/init", {
        method: "POST",
        body: JSON.stringify({ mode }),
    });
}

export async function endSession(sessionId: string): Promise<void> {
    return apiFetch(`/api/v1/session/${sessionId}/end`, { method: "POST" });
}

// ─── Voice ───────────────────────────────────────────────────

export interface VoiceToken {
    session_id: string;
    livekit_token: string;
    room_name: string;
}

export async function getVoiceToken(): Promise<VoiceToken> {
    return apiFetch("/api/v1/voice/token", { method: "POST" });
}

// ─── Dashboard ───────────────────────────────────────────────

export interface PersonalityProfile {
    user_id: string;
    jungian_type: string | null;
    type_confidence: number;
    trait_weights: Record<string, number>;
    attachment_style: string | null;
    cognitive_style: string | null;
    core_values: string[];
    version: number;
}

export async function getPersonality(): Promise<PersonalityProfile> {
    return apiFetch("/api/v1/dashboard/personality");
}

export interface DayActivity {
    date: string;
    session_count: number;
    turn_count: number;
    chat_turns: number;
    voice_turns: number;
}

export interface ActivityData {
    user_id: string;
    days: DayActivity[];
    total_sessions: number;
    total_turns: number;
}

export async function getActivity(days: number = 30): Promise<ActivityData> {
    return apiFetch(`/api/v1/dashboard/activity?days=${days}`);
}

export interface DiaryEntry {
    id: string;
    date: string;
    content: string;
    page_number: number;
    created_at: string;
}

export interface DiaryList {
    entries: DiaryEntry[];
    total: number;
    pages_owned: number;
    page: number;
    page_size: number;
}

export async function getDiary(page: number = 1): Promise<DiaryList> {
    return apiFetch(`/api/v1/dashboard/diary?page=${page}`);
}

export interface TraitItem {
    id: string;
    name: string;
    category: string;
    prompt_modifier: string;
    coin_cost: number;
    locked: boolean;
    is_active: boolean;
}

export interface TraitLibrary {
    traits: TraitItem[];
    active_trait_ids: string[];
}

export async function getTraits(): Promise<TraitLibrary> {
    return apiFetch("/api/v1/dashboard/traits");
}

// ─── Persona ─────────────────────────────────────────────────

export async function updateActiveTraits(traitIds: string[]): Promise<void> {
    return apiFetch("/api/v1/persona/active", {
        method: "PATCH",
        body: JSON.stringify({ active_trait_ids: traitIds }),
    });
}

// ─── Coins ───────────────────────────────────────────────────

export interface CoinBalance {
    total_coins: number;
    daily_earned_today: number;
    daily_cap: number;
    diary_pages_owned: number;
}

export async function getBalance(): Promise<CoinBalance> {
    return apiFetch("/api/v1/coins/balance");
}

export async function buyDiaryPage(): Promise<{ diary_pages_owned: number; total_coins: number }> {
    return apiFetch("/api/v1/coins/buy-diary-page", { method: "POST" });
}

// ─── WebSocket ───────────────────────────────────────────────

export function getChatWsUrl(sessionId: string): string {
    const token = getToken();
    const wsBase = API_BASE.replace("http", "ws");
    return `${wsBase}/ws/session/${sessionId}/chat?token=${token}`;
}
