import { useState, useRef } from "react";

export interface StoreScopedDataOptions<T> {
  fetcher: (storeId: string, signal: AbortSignal) => Promise<T>;
}

export function useStoreScopedData<T>({
  fetcher,
}: StoreScopedDataOptions<T>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeStoreId, setActiveStoreId] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const loadData = async (storeId: string) => {
    // 既存リクエストがあればキャンセル
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentRequestId = ++requestIdRef.current;

    // TC-105: 切替直後に旧店舗データを破棄
    setData(null);
    setLoading(true);
    setError(null);
    setActiveStoreId(storeId);

    try {
      const result = await fetcher(storeId, controller.signal);

      // TC-106: 後から返ってきた旧要求レスポンスなら無視して破棄
      if (currentRequestId === requestIdRef.current) {
        setData(result);
      }
    } catch (e: unknown) {
      if (controller.signal.aborted) {
        return;
      }
      if (currentRequestId === requestIdRef.current) {
        setError(e instanceof Error ? e.message : "データの取得に失敗しました。");
      }
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  };

  const clearData = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    requestIdRef.current++;
    setData(null);
    setError(null);
    setLoading(false);
    setActiveStoreId(null);
  };

  return {
    data,
    loading,
    error,
    activeStoreId,
    loadData,
    clearData,
  };
}
