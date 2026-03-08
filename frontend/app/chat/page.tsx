"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { initSession, endSession, getChatWsUrl } from "@/lib/api";

interface Message {
    id: string;
    role: "user" | "ai";
    content: string;
    streaming?: boolean;
}

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [connected, setConnected] = useState(false);
    const [loading, setLoading] = useState(true);
    const wsRef = useRef<WebSocket | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const streamingMsgRef = useRef<string>("");

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    // Init session and WebSocket on mount
    useEffect(() => {
        let ws: WebSocket | null = null;
        let sid: string | null = null;

        async function setup() {
            try {
                const session = await initSession("chat");
                sid = session.session_id;
                setSessionId(sid);

                const wsUrl = getChatWsUrl(sid);
                ws = new WebSocket(wsUrl);
                wsRef.current = ws;

                ws.onopen = () => {
                    setConnected(true);
                    setLoading(false);
                };

                ws.onmessage = (event) => {
                    const data = event.data;

                    if (data === "[EOR]") {
                        // End of response — finalize the streaming message
                        setMessages((prev) => {
                            const updated = [...prev];
                            const last = updated[updated.length - 1];
                            if (last && last.role === "ai" && last.streaming) {
                                updated[updated.length - 1] = { ...last, streaming: false };
                            }
                            return updated;
                        });
                        streamingMsgRef.current = "";
                        return;
                    }

                    // Streaming token
                    streamingMsgRef.current += data;

                    setMessages((prev) => {
                        const updated = [...prev];
                        const last = updated[updated.length - 1];

                        if (last && last.role === "ai" && last.streaming) {
                            // Append to existing streaming message
                            updated[updated.length - 1] = {
                                ...last,
                                content: streamingMsgRef.current,
                            };
                        } else {
                            // Start new AI message
                            updated.push({
                                id: `ai-${Date.now()}`,
                                role: "ai",
                                content: streamingMsgRef.current,
                                streaming: true,
                            });
                        }
                        return updated;
                    });
                };

                ws.onclose = () => {
                    setConnected(false);
                };

                ws.onerror = () => {
                    setConnected(false);
                    setLoading(false);
                };
            } catch (err) {
                console.error("Failed to init chat:", err);
                setLoading(false);
            }
        }

        setup();

        return () => {
            if (ws) ws.close();
            if (sid) endSession(sid).catch(() => { });
        };
    }, []);

    function handleSend() {
        if (!input.trim() || !wsRef.current || !connected) return;

        const userMsg: Message = {
            id: `user-${Date.now()}`,
            role: "user",
            content: input.trim(),
        };

        setMessages((prev) => [...prev, userMsg]);
        wsRef.current.send(input.trim());
        setInput("");
        streamingMsgRef.current = "";
    }

    function handleKeyDown(e: React.KeyboardEvent) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    if (loading) {
        return (
            <div className="chat-page">
                <div className="chat-avatar-panel">
                    <img src="/avatar.png" alt="Companion" className="chat-avatar-image" />
                </div>
                <div className="chat-panel">
                    <div className="empty-state" style={{ height: "100%" }}>
                        <div className="loading-spinner" />
                        <span>Connecting...</span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="chat-page">
            <div className="chat-avatar-panel">
                <img src="/avatar.png" alt="Companion" className="chat-avatar-image" />
            </div>

            <div className="chat-panel">
                <div className="chat-messages">
                    {messages.length === 0 && (
                        <div className="empty-state">
                            <span style={{ fontSize: "1.5rem" }}>💬</span>
                            <span>Say something to start the conversation</span>
                        </div>
                    )}

                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={`chat-message ${msg.role}${msg.streaming ? " streaming" : ""}`}
                        >
                            {msg.content}
                        </div>
                    ))}
                    <div ref={messagesEndRef} />
                </div>

                <div className="chat-input-area">
                    <input
                        className="chat-input"
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={connected ? "Type a message..." : "Disconnected"}
                        disabled={!connected}
                    />
                    <button
                        className="chat-send-btn"
                        onClick={handleSend}
                        disabled={!input.trim() || !connected}
                    >
                        ↑
                    </button>
                </div>
            </div>
        </div>
    );
}
