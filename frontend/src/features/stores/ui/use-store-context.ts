import { useState } from "react";
import type { SelectableStore } from "../model/selectable-store";

export interface UseStoreContextOptions {
  stores: readonly SelectableStore[];
  initialSelectedStoreId: string | null;
  onSelectStore: (storeId: string) => Promise<void>;
  onClearPreviousStoreData?: () => void;
}

export function useStoreContext({
  stores,
  initialSelectedStoreId,
  onSelectStore,
  onClearPreviousStoreData,
}: UseStoreContextOptions) {
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(
    initialSelectedStoreId,
  );
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const switchStore = async (targetStoreId: string) => {
    if (targetStoreId === selectedStoreId) {
      return;
    }

    // TC-105: 切替直後に旧店舗(A1)のデータを即座に破棄
    if (onClearPreviousStoreData) {
      onClearPreviousStoreData();
    }

    setSwitching(true);
    setError(null);

    try {
      await onSelectStore(targetStoreId);
      setSelectedStoreId(targetStoreId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "店舗の切り替えに失敗しました。");
      throw e;
    } finally {
      setSwitching(false);
    }
  };

  return {
    stores,
    selectedStoreId,
    switching,
    error,
    switchStore,
  };
}
