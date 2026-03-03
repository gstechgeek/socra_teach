import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type ConceptNode, type StatsResponse } from "../hooks/useProgress";

// ── Types ──────────────────────────────────────────────────────────────────

interface ProgressDashboardProps {
  stats: StatsResponse | null;
  concepts: ConceptNode[];
}

// ── Stat card ──────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 120,
        background: "#161823",
        border: "1px solid #1e2030",
        borderRadius: 8,
        padding: "0.75rem 1rem",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "1.5rem", fontWeight: 600, color }}>{value}</div>
      <div style={{ fontSize: "0.72rem", color: "#7c84a0", marginTop: "0.2rem" }}>{label}</div>
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

/**
 * ProgressDashboard shows stats cards, a review activity bar chart,
 * and concept mastery distribution.
 */
export function ProgressDashboard({ stats, concepts }: ProgressDashboardProps) {
  const today = stats?.today;

  // Chart data: last 30 days of reviews
  const chartData = useMemo(() => {
    if (!stats?.history) return [];
    return stats.history.map((d) => ({
      date: d.date.slice(5), // MM-DD
      reviews: d.reviews_completed,
      created: d.cards_created,
    }));
  }, [stats]);

  // Mastery distribution
  const masteryDist = useMemo(() => {
    const counts = { not_started: 0, learning: 0, practiced: 0, mastered: 0 };
    for (const c of concepts) {
      counts[c.mastery]++;
    }
    return [
      { level: "Not Started", count: counts.not_started, color: "#7c84a0" },
      { level: "Learning", count: counts.learning, color: "#ef4444" },
      { level: "Practiced", count: counts.practiced, color: "#f59e0b" },
      { level: "Mastered", count: counts.mastered, color: "#22c55e" },
    ];
  }, [concepts]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", padding: "1.5rem" }}>
      {/* Stats cards row */}
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <StatCard
          label="Streak Days"
          value={today?.streak_days ?? 0}
          color="#f59e0b"
        />
        <StatCard
          label="Reviews Today"
          value={today?.reviews_completed ?? 0}
          color="#3b82f6"
        />
        <StatCard
          label="Cards Created"
          value={today?.cards_created ?? 0}
          color="#22c55e"
        />
        <StatCard
          label="Total Concepts"
          value={concepts.length}
          color="#c4b5fd"
        />
      </div>

      {/* Review activity chart */}
      {chartData.length > 0 && (
        <div
          style={{
            background: "#161823",
            border: "1px solid #1e2030",
            borderRadius: 8,
            padding: "1rem",
          }}
        >
          <div
            style={{
              fontSize: "0.8rem",
              color: "#7c84a0",
              marginBottom: "0.75rem",
              fontWeight: 500,
            }}
          >
            Review Activity (Last 30 Days)
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2030" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#555", fontSize: 10 }}
                axisLine={{ stroke: "#1e2030" }}
              />
              <YAxis
                tick={{ fill: "#555", fontSize: 10 }}
                axisLine={{ stroke: "#1e2030" }}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#0f1117",
                  border: "1px solid #1e2030",
                  borderRadius: 6,
                  fontSize: "0.75rem",
                }}
                labelStyle={{ color: "#7c84a0" }}
              />
              <Bar dataKey="reviews" fill="#3b82f6" radius={[2, 2, 0, 0]} name="Reviews" />
              <Bar dataKey="created" fill="#22c55e" radius={[2, 2, 0, 0]} name="Cards Created" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Concept mastery distribution */}
      {concepts.length > 0 && (
        <div
          style={{
            background: "#161823",
            border: "1px solid #1e2030",
            borderRadius: 8,
            padding: "1rem",
          }}
        >
          <div
            style={{
              fontSize: "0.8rem",
              color: "#7c84a0",
              marginBottom: "0.75rem",
              fontWeight: 500,
            }}
          >
            Concept Mastery
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            {masteryDist.map((m) => (
              <div key={m.level} style={{ flex: 1, textAlign: "center" }}>
                <div style={{ fontSize: "1.25rem", fontWeight: 600, color: m.color }}>
                  {m.count}
                </div>
                <div style={{ fontSize: "0.65rem", color: "#7c84a0" }}>{m.level}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
