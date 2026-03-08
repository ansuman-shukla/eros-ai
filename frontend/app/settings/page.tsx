"use client";

import { useState, useEffect } from "react";
import {
    getTraits,
    getBalance,
    updateActiveTraits,
    buyDiaryPage,
    type TraitItem,
    type TraitLibrary,
    type CoinBalance,
} from "@/lib/api";

export default function SettingsPage() {
    const [traits, setTraits] = useState<TraitLibrary | null>(null);
    const [balance, setBalance] = useState<CoinBalance | null>(null);
    const [activeIds, setActiveIds] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [buying, setBuying] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function load() {
            try {
                const [t, b] = await Promise.all([getTraits(), getBalance()]);
                setTraits(t);
                setBalance(b);
                setActiveIds(t.active_trait_ids);
            } catch (err) {
                console.error("Settings load error:", err);
            } finally {
                setLoading(false);
            }
        }
        load();
    }, []);

    async function toggleTrait(name: string) {
        const next = activeIds.includes(name)
            ? activeIds.filter((id) => id !== name)
            : [...activeIds, name];

        setActiveIds(next);
        setSaving(true);
        try {
            await updateActiveTraits(next);
        } catch (err) {
            console.error("Failed to update traits:", err);
            // Revert
            setActiveIds(activeIds);
        } finally {
            setSaving(false);
        }
    }

    async function handleBuyPage() {
        setBuying(true);
        try {
            const result = await buyDiaryPage();
            setBalance((prev) =>
                prev
                    ? {
                        ...prev,
                        total_coins: result.total_coins,
                        diary_pages_owned: result.diary_pages_owned,
                    }
                    : prev
            );
        } catch (err: any) {
            alert(err.message || "Not enough coins");
        } finally {
            setBuying(false);
        }
    }

    if (loading) {
        return (
            <div className="settings-page">
                <div className="empty-state">
                    <div className="loading-spinner" />
                </div>
            </div>
        );
    }

    // Group traits by category
    const categories = new Map<string, TraitItem[]>();
    traits?.traits.forEach((t) => {
        const list = categories.get(t.category) || [];
        list.push(t);
        categories.set(t.category, list);
    });

    return (
        <div className="settings-page">
            {/* Coin Balance */}
            <div className="settings-section">
                <h2>Coins</h2>
                <div className="coin-display">
                    <div>
                        <div className="coin-amount">{balance?.total_coins ?? 0}</div>
                        <div className="coin-label">
                            {balance?.daily_earned_today ?? 0} / {balance?.daily_cap ?? 100} earned today
                        </div>
                    </div>
                    <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
                        <div style={{ textAlign: "right" }}>
                            <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                                {balance?.diary_pages_owned ?? 5} pages
                            </div>
                            <div className="coin-label">diary pages owned</div>
                        </div>
                        <button
                            className="btn-primary"
                            onClick={handleBuyPage}
                            disabled={buying || (balance?.total_coins ?? 0) < 50}
                        >
                            {buying ? "..." : "Buy page (50)"}
                        </button>
                    </div>
                </div>
            </div>

            {/* Persona Traits */}
            <div className="settings-section">
                <h2>
                    Persona Traits
                    {saving && (
                        <span style={{ marginLeft: 8, fontSize: "0.7rem", color: "var(--accent)", fontWeight: 400 }}>
                            saving...
                        </span>
                    )}
                </h2>

                {Array.from(categories.entries()).map(([category, traitList]) => (
                    <div key={category} style={{ marginBottom: 20 }}>
                        <div style={{
                            fontSize: "0.75rem",
                            color: "var(--text-muted)",
                            textTransform: "capitalize",
                            marginBottom: 8,
                        }}>
                            {category}
                        </div>
                        <div className="trait-grid">
                            {traitList.map((trait) => (
                                <button
                                    key={trait.id}
                                    className={`trait-chip ${activeIds.includes(trait.name) ? "active" : ""} ${trait.locked ? "locked" : ""}`}
                                    onClick={() => !trait.locked && toggleTrait(trait.name)}
                                    disabled={trait.locked}
                                >
                                    <span>{trait.name}</span>
                                    {trait.coin_cost > 0 && (
                                        <span className="trait-chip-cost">{trait.coin_cost}c</span>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
