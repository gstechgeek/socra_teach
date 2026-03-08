import { useCallback, useRef, useState } from "react";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface UseRectSelectReturn {
  /** Whether selection mode is active. */
  isSelecting: boolean;
  /** Toggle selection mode on/off. */
  toggleSelecting: () => void;
  /** The current (or final) rectangle in container-relative px. */
  rect: Rect | null;
  /** Clear the current selection. */
  clearRect: () => void;
  /** Attach to the overlay container element. */
  onMouseDown: (e: React.MouseEvent) => void;
  onMouseMove: (e: React.MouseEvent) => void;
  onMouseUp: (e: React.MouseEvent) => void;
}

/**
 * Hook that tracks a mouse-drag rectangle selection on an overlay element.
 *
 * Returns handlers to attach to the overlay div and the resulting rect
 * in container-relative coordinates.
 */
export function useRectSelect(): UseRectSelectReturn {
  const [isSelecting, setIsSelecting] = useState(false);
  const [rect, setRect] = useState<Rect | null>(null);
  const originRef = useRef<{ x: number; y: number } | null>(null);
  const draggingRef = useRef(false);

  const toggleSelecting = useCallback(() => {
    setIsSelecting((prev) => {
      if (prev) {
        // Turning off — clear any selection
        setRect(null);
        originRef.current = null;
        draggingRef.current = false;
      }
      return !prev;
    });
  }, []);

  const clearRect = useCallback(() => {
    setRect(null);
    originRef.current = null;
    draggingRef.current = false;
  }, []);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!isSelecting) return;
      e.preventDefault();
      const container = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - container.left;
      const y = e.clientY - container.top;
      originRef.current = { x, y };
      draggingRef.current = true;
      setRect({ x, y, width: 0, height: 0 });
    },
    [isSelecting],
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!draggingRef.current || !originRef.current) return;
      const container = e.currentTarget.getBoundingClientRect();
      const cx = e.clientX - container.left;
      const cy = e.clientY - container.top;
      const ox = originRef.current.x;
      const oy = originRef.current.y;
      setRect({
        x: Math.min(ox, cx),
        y: Math.min(oy, cy),
        width: Math.abs(cx - ox),
        height: Math.abs(cy - oy),
      });
    },
    [],
  );

  const onMouseUp = useCallback(() => {
    draggingRef.current = false;
  }, []);

  return { isSelecting, toggleSelecting, rect, clearRect, onMouseDown, onMouseMove, onMouseUp };
}
