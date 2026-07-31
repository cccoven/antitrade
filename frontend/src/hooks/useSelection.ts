import { useCallback, useRef, useState } from "react";

export interface UseSelectionApi {
  selectedIds: Set<string>;
  allMatching: boolean;
  isSelected(id: string): boolean;
  toggle(id: string): void;
  toggleAllOnPage(pageIds: string[]): void;
  shiftSelect(id: string, pageIds: string[]): void;
  selectAllMatching(): void;
  clear(): void;
  count(totalMatching: number): number;
}

export function useSelection(): UseSelectionApi {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [allMatching, setAllMatching] = useState(false);
  const lastSelectedIdRef = useRef<string | null>(null);

  const isSelected = useCallback(
    (id: string) => allMatching || selectedIds.has(id),
    [allMatching, selectedIds],
  );

  const toggle = useCallback((id: string) => {
    setAllMatching(false);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    lastSelectedIdRef.current = id;
  }, []);

  const toggleAllOnPage = useCallback((pageIds: string[]) => {
    setAllMatching(false);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const allSelected = pageIds.every((id) => next.has(id));
      if (allSelected) {
        for (const id of pageIds) next.delete(id);
      } else {
        for (const id of pageIds) next.add(id);
      }
      return next;
    });
  }, []);

  const shiftSelect = useCallback((id: string, pageIds: string[]) => {
    const anchor = lastSelectedIdRef.current;
    if (!anchor) {
      // No anchor yet — degrade to a single toggle
      setAllMatching(false);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      lastSelectedIdRef.current = id;
      return;
    }
    const anchorIdx = pageIds.indexOf(anchor);
    const targetIdx = pageIds.indexOf(id);
    if (anchorIdx === -1 || targetIdx === -1) {
      // Anchor not on this page — fall back to single toggle
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      lastSelectedIdRef.current = id;
      return;
    }
    const [lo, hi] = anchorIdx < targetIdx ? [anchorIdx, targetIdx] : [targetIdx, anchorIdx];
    setAllMatching(false);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (let i = lo; i <= hi; i += 1) next.add(pageIds[i]);
      return next;
    });
    lastSelectedIdRef.current = id;
  }, []);

  const selectAllMatching = useCallback(() => {
    setAllMatching(true);
  }, []);

  const clear = useCallback(() => {
    setAllMatching(false);
    setSelectedIds(new Set());
    lastSelectedIdRef.current = null;
  }, []);

  const count = useCallback(
    (totalMatching: number) => (allMatching ? totalMatching : selectedIds.size),
    [allMatching, selectedIds],
  );

  return {
    selectedIds,
    allMatching,
    isSelected,
    toggle,
    toggleAllOnPage,
    shiftSelect,
    selectAllMatching,
    clear,
    count,
  };
}
