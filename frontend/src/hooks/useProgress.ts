import { useCallback, useEffect, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

export interface ConceptNode {
  concept_id: string;
  name: string;
  description: string;
  p_know: number;
  mastery: "not_started" | "learning" | "practiced" | "mastered";
  total_attempts: number;
  correct_attempts: number;
}

export interface ConceptEdge {
  concept_id: string;
  prerequisite_id: string;
}

export interface DailyStats {
  date: string;
  reviews_completed: number;
  cards_created: number;
  concepts_learned: number;
  streak_days: number;
  session_minutes: number;
}

export interface StatsResponse {
  today: DailyStats;
  history: DailyStats[];
}

interface ConceptGraphResponse {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
}

interface UseProgressReturn {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
  stats: StatsResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

// ── Hook ───────────────────────────────────────────────────────────────────

/**
 * Fetches concept graph and daily stats from the progress API.
 * Automatically refreshes on mount.
 */
export function useProgress(): UseProgressReturn {
  const [concepts, setConcepts] = useState<ConceptNode[]>([]);
  const [edges, setEdges] = useState<ConceptEdge[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setIsLoading(true);
    setError(null);

    Promise.all([
      fetch("/api/progress/concepts").then((r) => {
        if (!r.ok) throw new Error(`concepts: ${r.status}`);
        return r.json() as Promise<ConceptGraphResponse>;
      }),
      fetch("/api/progress/stats").then((r) => {
        if (!r.ok) throw new Error(`stats: ${r.status}`);
        return r.json() as Promise<StatsResponse>;
      }),
    ])
      .then(([graph, statsData]) => {
        setConcepts(graph.concepts);
        setEdges(graph.edges);
        setStats(statsData);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Unknown error";
        setError(msg);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { concepts, edges, stats, isLoading, error, refresh };
}
