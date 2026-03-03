import { useState } from "react";
import { ConceptGraph } from "../components/ConceptGraph";
import { ProgressDashboard } from "../components/ProgressDashboard";
import { ReviewSession } from "../components/ReviewSession";
import { useProgress } from "../hooks/useProgress";

type Tab = "review" | "dashboard";

/**
 * ProgressPage provides two sub-tabs:
 * - Review: flashcard review session (FSRS)
 * - Dashboard: stats, charts, and concept graph
 */
export function ProgressPage() {
  const [tab, setTab] = useState<Tab>("review");
  const { concepts, edges, stats, isLoading, error, refresh } = useProgress();

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#0f1117",
        color: "#e8eaf0",
      }}
    >
      {/* Header with sub-tabs */}
      <header
        style={{
          padding: "0.5rem 1.25rem",
          borderBottom: "1px solid #1e2030",
          display: "flex",
          alignItems: "center",
          gap: "1.5rem",
        }}
      >
        <span style={{ fontSize: "0.85rem", color: "#7c84a0", marginRight: "auto" }}>
          Progress
        </span>

        {(["review", "dashboard"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              if (t === "dashboard") refresh();
            }}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "0.8rem",
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? "#e8eaf0" : "#7c84a0",
              padding: "0.25rem 0",
              borderBottom: tab === t ? "2px solid #2563eb" : "2px solid transparent",
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {t === "review" ? "Review" : "Dashboard"}
          </button>
        ))}
      </header>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {tab === "review" && <ReviewSession />}

        {tab === "dashboard" && (
          <>
            {isLoading && (
              <div
                style={{
                  textAlign: "center",
                  color: "#7c84a0",
                  padding: "2rem",
                  fontSize: "0.85rem",
                }}
              >
                Loading progress data...
              </div>
            )}

            {error && (
              <div
                style={{
                  textAlign: "center",
                  color: "#ef4444",
                  padding: "2rem",
                  fontSize: "0.85rem",
                }}
              >
                Error: {error}
              </div>
            )}

            {!isLoading && !error && (
              <>
                <ProgressDashboard stats={stats} concepts={concepts} />
                <div style={{ padding: "0 1.5rem 1.5rem" }}>
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "#7c84a0",
                      marginBottom: "0.75rem",
                      fontWeight: 500,
                    }}
                  >
                    Knowledge Graph
                  </div>
                  <ConceptGraph concepts={concepts} edges={edges} />
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
