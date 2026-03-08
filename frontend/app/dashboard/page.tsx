"use client";

import { useState, useEffect } from "react";
import {
    getPersonality,
    getActivity,
    getDiary,
    type PersonalityProfile,
    type ActivityData,
    type DiaryList,
} from "@/lib/api";

export default function DashboardPage() {
    const [personality, setPersonality] = useState<PersonalityProfile | null>(null);
    const [activity, setActivity] = useState<ActivityData | null>(null);
    const [diary, setDiary] = useState<DiaryList | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [p, a, d] = await Promise.all([
                    getPersonality(),
                    getActivity(),
                    getDiary(),
                ]);
                setPersonality(p);
                setActivity(a);
                setDiary(d);
            } catch (err) {
                console.error("Dashboard load error:", err);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    if (loading) {
        return (
            <div className="dashboard-page">
                <div className="empty-state">
                    <div className="loading-spinner" />
                </div>
            </div>
        );
    }

    // Get top traits (weight > 0.2) sorted by weight
    const topTraits = personality
        ? Object.entries(personality.trait_weights)
            .filter(([, v]) => v > 0.2)
            .sort(([, a], [, b]) => b - a)
            .slice(0, 10)
        : [];

    // Build activity grid (last 28 days = 4 weeks)
    const activityCells = buildActivityGrid(activity);

    return (
        <div className="dashboard-page">
            <div className="dashboard-header">
                <h1>Dashboard</h1>
                <p>Your personality insights and activity</p>
            </div>

            <div className="dashboard-grid">
                {/* Personality Card */}
                <div className="dashboard-card">
                    <h2>Personality</h2>
                    {personality?.jungian_type ? (
                        <>
                            <div className="personality-type">{personality.jungian_type}</div>
                            <div className="personality-confidence">
                                {(personality.type_confidence * 100).toFixed(0)}% confidence
                                {personality.attachment_style && ` · ${personality.attachment_style}`}
                            </div>
                            {personality.core_values.length > 0 && (
                                <div style={{ marginTop: 16, fontSize: "0.83rem", color: "var(--text-secondary)" }}>
                                    Core values: {personality.core_values.join(", ")}
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="empty-state" style={{ padding: "24px 0" }}>
                            <span>Keep chatting to build your profile</span>
                        </div>
                    )}
                </div>

                {/* Trait Weights Card */}
                <div className="dashboard-card">
                    <h2>Top Traits</h2>
                    {topTraits.length > 0 ? (
                        topTraits.map(([name, weight]) => (
                            <div key={name} className="trait-bar">
                                <span className="trait-bar-label">
                                    {name.replace(/_/g, " ")}
                                </span>
                                <div className="trait-bar-track">
                                    <div
                                        className="trait-bar-fill"
                                        style={{ width: `${(weight as number) * 100}%` }}
                                    />
                                </div>
                                <span className="trait-bar-value">
                                    {((weight as number) * 100).toFixed(0)}
                                </span>
                            </div>
                        ))
                    ) : (
                        <div className="empty-state" style={{ padding: "24px 0" }}>
                            <span>No dominant traits yet</span>
                        </div>
                    )}
                </div>

                {/* Activity Card */}
                <div className="dashboard-card">
                    <h2>Activity</h2>
                    <div style={{ marginBottom: 12, fontSize: "0.83rem", color: "var(--text-secondary)" }}>
                        {activity?.total_sessions || 0} sessions · {activity?.total_turns || 0} turns
                    </div>
                    <div className="activity-grid">
                        {activityCells.map((level, i) => (
                            <div key={i} className={`activity-cell level-${level}`} />
                        ))}
                    </div>
                </div>

                {/* Diary Card */}
                <div className="dashboard-card">
                    <h2>Diary</h2>
                    {diary && diary.entries.length > 0 ? (
                        <>
                            {diary.entries.slice(0, 5).map((entry) => (
                                <div key={entry.id} className="diary-entry">
                                    <div className="diary-entry-date">{entry.date}</div>
                                    <div className="diary-entry-content">{entry.content}</div>
                                </div>
                            ))}
                            {diary.total > 5 && (
                                <div style={{ marginTop: 12, fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                    {diary.total - 5} more entries · {diary.pages_owned} pages owned
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="empty-state" style={{ padding: "24px 0" }}>
                            <span>No diary entries yet</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function buildActivityGrid(activity: ActivityData | null): number[] {
    // Build 28 cells (4 weeks) showing activity levels 0-4
    const cells: number[] = new Array(28).fill(0);

    if (!activity?.days) return cells;

    const today = new Date();
    const dayMap = new Map(activity.days.map((d) => [d.date, d.turn_count]));

    for (let i = 0; i < 28; i++) {
        const date = new Date(today);
        date.setDate(date.getDate() - (27 - i));
        const key = date.toISOString().split("T")[0];
        const turns = dayMap.get(key) || 0;

        if (turns === 0) cells[i] = 0;
        else if (turns <= 5) cells[i] = 1;
        else if (turns <= 15) cells[i] = 2;
        else if (turns <= 30) cells[i] = 3;
        else cells[i] = 4;
    }

    return cells;
}
