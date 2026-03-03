import { useEffect } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import { useReviewQueue } from "../hooks/useReviewQueue";

// ── Rating button config ───────────────────────────────────────────────────

const RATINGS = [
  { value: 1, label: "Again", color: "#ef4444", bg: "#3b1111" },
  { value: 2, label: "Hard", color: "#f59e0b", bg: "#3b2f11" },
  { value: 3, label: "Good", color: "#3b82f6", bg: "#111c3b" },
  { value: 4, label: "Easy", color: "#22c55e", bg: "#113b1c" },
] as const;

// ── Component ──────────────────────────────────────────────────────────────

/**
 * ReviewSession manages a flashcard review queue.
 * Shows one card at a time: front -> flip -> back -> rate -> next.
 */
export function ReviewSession() {
  const {
    cards,
    currentIndex,
    isFlipped,
    isComplete,
    isLoading,
    loadDueCards,
    flip,
    submitRating,
  } = useReviewQueue();

  useEffect(() => {
    loadDueCards();
  }, [loadDueCards]);

  // Loading state
  if (isLoading) {
    return (
      <div style={centerStyle}>
        <span style={{ color: "#7c84a0", fontSize: "0.9rem" }}>
          Loading review cards...
        </span>
      </div>
    );
  }

  // Session complete or no cards
  if (isComplete) {
    return (
      <div style={centerStyle}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "0.75rem", color: "#e8eaf0" }}>
            {cards.length === 0 ? "No cards due for review" : "Session complete!"}
          </div>
          <div style={{ fontSize: "0.85rem", color: "#7c84a0", marginBottom: "1.5rem" }}>
            {cards.length === 0
              ? "Chat with the tutor to generate flashcards."
              : `You reviewed ${cards.length} card${cards.length === 1 ? "" : "s"}.`}
          </div>
          <button
            onClick={loadDueCards}
            style={{
              padding: "0.5rem 1.5rem",
              background: "#2563eb",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            {cards.length === 0 ? "Refresh" : "Review Again"}
          </button>
        </div>
      </div>
    );
  }

  const card = cards[currentIndex];
  if (!card) return null;

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "2rem 1.5rem",
        gap: "1.5rem",
      }}
    >
      {/* Progress indicator */}
      <div style={{ fontSize: "0.8rem", color: "#7c84a0" }}>
        Card {currentIndex + 1} of {cards.length}
      </div>

      {/* Progress bar */}
      <div
        style={{
          width: "100%",
          maxWidth: 500,
          height: 4,
          background: "#1e2030",
          borderRadius: 2,
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${((currentIndex) / cards.length) * 100}%`,
            background: "#2563eb",
            borderRadius: 2,
            transition: "width 0.3s ease",
          }}
        />
      </div>

      {/* Card */}
      <div
        onClick={!isFlipped ? flip : undefined}
        style={{
          width: "100%",
          maxWidth: 500,
          minHeight: 240,
          background: "#161823",
          border: "1px solid #1e2030",
          borderRadius: 12,
          padding: "2rem",
          cursor: !isFlipped ? "pointer" : "default",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
          transition: "border-color 0.15s",
        }}
      >
        <div
          style={{
            fontSize: "0.7rem",
            color: "#555",
            marginBottom: "1rem",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          {isFlipped ? "Answer" : "Question"}
        </div>

        <div style={{ fontSize: "1rem", color: "#e8eaf0", lineHeight: 1.6 }}>
          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
            {isFlipped ? card.back : card.front}
          </ReactMarkdown>
        </div>

        {!isFlipped && (
          <div style={{ marginTop: "1.5rem", fontSize: "0.75rem", color: "#555" }}>
            Click to reveal answer
          </div>
        )}
      </div>

      {/* Rating buttons — only visible when flipped */}
      {isFlipped && (
        <div style={{ display: "flex", gap: "0.75rem" }}>
          {RATINGS.map((r) => (
            <button
              key={r.value}
              onClick={() => void submitRating(r.value)}
              style={{
                padding: "0.6rem 1.25rem",
                background: r.bg,
                color: r.color,
                border: `1px solid ${r.color}33`,
                borderRadius: 8,
                cursor: "pointer",
                fontSize: "0.85rem",
                fontWeight: 500,
                transition: "opacity 0.15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.opacity = "0.8";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.opacity = "1";
              }}
            >
              {r.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const centerStyle: React.CSSProperties = {
  height: "100%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
