import { useMemo } from "react";
import { type ConceptEdge, type ConceptNode } from "../hooks/useProgress";

// ── Mastery badge colors ───────────────────────────────────────────────────

const MASTERY_COLORS: Record<ConceptNode["mastery"], { bg: string; text: string; label: string }> =
  {
    not_started: { bg: "#2a2d3a", text: "#7c84a0", label: "Not Started" },
    learning: { bg: "#3b1111", text: "#ef4444", label: "Learning" },
    practiced: { bg: "#3b2f11", text: "#f59e0b", label: "Practiced" },
    mastered: { bg: "#113b1c", text: "#22c55e", label: "Mastered" },
  };

interface ConceptGraphProps {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
}

// ── Topological sort ───────────────────────────────────────────────────────

function topoSort(concepts: ConceptNode[], edges: ConceptEdge[]): ConceptNode[] {
  const byId = new Map(concepts.map((c) => [c.concept_id, c]));
  const children = new Map<string, string[]>();
  const inDegree = new Map<string, number>();

  for (const c of concepts) {
    children.set(c.concept_id, []);
    inDegree.set(c.concept_id, 0);
  }
  for (const e of edges) {
    children.get(e.prerequisite_id)?.push(e.concept_id);
    inDegree.set(e.concept_id, (inDegree.get(e.concept_id) ?? 0) + 1);
  }

  const queue = concepts.filter((c) => (inDegree.get(c.concept_id) ?? 0) === 0);
  const sorted: ConceptNode[] = [];

  while (queue.length > 0) {
    const node = queue.shift()!;
    sorted.push(node);
    for (const childId of children.get(node.concept_id) ?? []) {
      const deg = (inDegree.get(childId) ?? 1) - 1;
      inDegree.set(childId, deg);
      const child = byId.get(childId);
      if (deg === 0 && child) queue.push(child);
    }
  }

  // Append any remaining nodes not reached by topo sort (cycles, orphans)
  const seen = new Set(sorted.map((c) => c.concept_id));
  for (const c of concepts) {
    if (!seen.has(c.concept_id)) sorted.push(c);
  }
  return sorted;
}

// ── Component ──────────────────────────────────────────────────────────────

/**
 * ConceptGraph renders a topologically-sorted list of concepts with
 * mastery badges and prerequisite relationships.
 */
export function ConceptGraph({ concepts, edges }: ConceptGraphProps) {
  const sorted = useMemo(() => topoSort(concepts, edges), [concepts, edges]);

  const prereqNames = useMemo(() => {
    const byId = new Map(concepts.map((c) => [c.concept_id, c.name]));
    const map = new Map<string, string[]>();
    for (const e of edges) {
      const list = map.get(e.concept_id) ?? [];
      const name = byId.get(e.prerequisite_id);
      if (name) list.push(name);
      map.set(e.concept_id, list);
    }
    return map;
  }, [concepts, edges]);

  if (concepts.length === 0) {
    return (
      <div
        style={{
          textAlign: "center",
          color: "#555",
          fontSize: "0.85rem",
          padding: "3rem 0",
        }}
      >
        No concepts discovered yet. Chat with the tutor to build your knowledge graph.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {sorted.map((concept) => {
        const mc = MASTERY_COLORS[concept.mastery];
        const prereqs = prereqNames.get(concept.concept_id);

        return (
          <div
            key={concept.concept_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.75rem",
              padding: "0.6rem 0.9rem",
              background: "#161823",
              border: "1px solid #1e2030",
              borderRadius: 8,
            }}
          >
            {/* Mastery badge */}
            <span
              style={{
                padding: "0.15rem 0.5rem",
                borderRadius: 4,
                fontSize: "0.65rem",
                fontWeight: 500,
                background: mc.bg,
                color: mc.text,
                whiteSpace: "nowrap",
                minWidth: 72,
                textAlign: "center",
              }}
            >
              {mc.label}
            </span>

            {/* Concept info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: "0.85rem",
                  color: "#e8eaf0",
                  fontWeight: 500,
                }}
              >
                {concept.name.replace(/_/g, " ")}
              </div>
              {concept.description && (
                <div style={{ fontSize: "0.72rem", color: "#7c84a0", marginTop: "0.15rem" }}>
                  {concept.description}
                </div>
              )}
              {prereqs && prereqs.length > 0 && (
                <div style={{ fontSize: "0.65rem", color: "#555", marginTop: "0.15rem" }}>
                  Requires: {prereqs.map((p) => p.replace(/_/g, " ")).join(", ")}
                </div>
              )}
            </div>

            {/* p_know bar */}
            <div style={{ width: 60, textAlign: "right" }}>
              <div style={{ fontSize: "0.7rem", color: "#7c84a0", marginBottom: "0.2rem" }}>
                {Math.round(concept.p_know * 100)}%
              </div>
              <div
                style={{
                  height: 4,
                  background: "#1e2030",
                  borderRadius: 2,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${concept.p_know * 100}%`,
                    background: mc.text,
                    borderRadius: 2,
                  }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
