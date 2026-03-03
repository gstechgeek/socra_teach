import { useCallback, useRef, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ReviewCard {
  card_id: string;
  front: string;
  back: string;
  concept_id: string;
  state: number;
  due: string;
  stability: number;
  difficulty: number;
  reps: number;
  lapses: number;
  created_at: string;
}

interface UseReviewQueueReturn {
  /** Cards in the current review session. */
  cards: ReviewCard[];
  /** Index of the card currently being reviewed. */
  currentIndex: number;
  /** Whether the card is flipped to show the back. */
  isFlipped: boolean;
  /** Whether the session is complete (all cards reviewed). */
  isComplete: boolean;
  /** Whether the queue is loading from the API. */
  isLoading: boolean;
  /** Fetch due cards from the API and start a review session. */
  loadDueCards: () => void;
  /** Flip the current card to show the back. */
  flip: () => void;
  /** Submit a rating (1-4) for the current card and advance. */
  submitRating: (rating: number) => Promise<void>;
}

// ── Hook ───────────────────────────────────────────────────────────────────

/**
 * Manages a flashcard review session: loads due cards, tracks flip state,
 * submits ratings with duration, and advances through the queue.
 */
export function useReviewQueue(): UseReviewQueueReturn {
  const [cards, setCards] = useState<ReviewCard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const flipTimeRef = useRef<number>(Date.now());

  const loadDueCards = useCallback(() => {
    setIsLoading(true);
    setIsComplete(false);
    setCurrentIndex(0);
    setIsFlipped(false);

    fetch("/api/progress/cards/due")
      .then((r) => {
        if (!r.ok) throw new Error(`due cards: ${r.status}`);
        return r.json() as Promise<ReviewCard[]>;
      })
      .then((data) => {
        setCards(data);
        if (data.length === 0) setIsComplete(true);
        flipTimeRef.current = Date.now();
      })
      .catch((err: unknown) => {
        console.error("Failed to load due cards", err);
        setCards([]);
        setIsComplete(true);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const flip = useCallback(() => {
    setIsFlipped(true);
    flipTimeRef.current = Date.now();
  }, []);

  const submitRating = useCallback(
    async (rating: number) => {
      const card = cards[currentIndex];
      if (!card) return;

      const durationMs = Date.now() - flipTimeRef.current;

      try {
        const resp = await fetch(`/api/progress/cards/${card.card_id}/review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating, duration_ms: durationMs }),
        });
        if (!resp.ok) {
          console.error("Review failed", resp.status);
        }
      } catch (err) {
        console.error("Review request failed", err);
      }

      const nextIndex = currentIndex + 1;
      if (nextIndex >= cards.length) {
        setIsComplete(true);
      } else {
        setCurrentIndex(nextIndex);
        setIsFlipped(false);
        flipTimeRef.current = Date.now();
      }
    },
    [cards, currentIndex],
  );

  return {
    cards,
    currentIndex,
    isFlipped,
    isComplete,
    isLoading,
    loadDueCards,
    flip,
    submitRating,
  };
}
