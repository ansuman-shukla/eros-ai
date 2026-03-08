"use client";

import { useState } from "react";
import { getVoiceToken } from "@/lib/api";

export default function VoicePage() {
    const [active, setActive] = useState(false);
    const [status, setStatus] = useState("Tap to start a voice call");
    const [sessionId, setSessionId] = useState<string | null>(null);

    async function handleStart() {
        try {
            setStatus("Connecting...");
            const { session_id, room_name } = await getVoiceToken();
            setSessionId(session_id);
            setActive(true);
            setStatus("Connected — speak naturally");
        } catch (err: any) {
            setStatus("Failed to connect");
            console.error(err);
        }
    }

    function handleEnd() {
        setActive(false);
        setSessionId(null);
        setStatus("Call ended");
        setTimeout(() => setStatus("Tap to start a voice call"), 2000);
    }

    return (
        <div className="voice-page">
            <div className="voice-container">
                <div className={`voice-avatar ${active ? "active" : ""}`}>
                    <img src="/avatar.png" alt="Companion" />
                </div>

                <p className={`voice-status ${active ? "active" : ""}`}>
                    {status}
                </p>

                {!active ? (
                    <button className="voice-btn start" onClick={handleStart}>
                        🎤
                    </button>
                ) : (
                    <button className="voice-btn end" onClick={handleEnd}>
                        ✕
                    </button>
                )}

                <div className="voice-transcript">
                    {active && (
                        <span style={{ color: "var(--text-muted)" }}>
                            Listening...
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}
