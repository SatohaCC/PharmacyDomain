import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useStoreContext } from "../src/features/stores/ui/use-store-context";
import { useStoreScopedData } from "../src/features/stores/ui/use-store-scoped-data";
import { accessToken, setAccessToken } from "../src/features/auth/api/session";
import type { SelectableStore } from "../src/features/stores/model/selectable-store";

describe("Phase 5 Work Unit 5c: 店舗切替・キャッシュ破棄・遅延制御・複数タブ (TC-104〜TC-107)", () => {
  const stores: SelectableStore[] = [
    { id: "store-a1", name: "テスト薬局 A1本店", code: "A01" },
    { id: "store-a2", name: "テスト薬局 A2駅前店", code: "A02" },
  ];

  beforeEach(() => {
    sessionStorage.clear();
    setAccessToken("");
  });

  describe("TC-104: 店舗選択・切替と新トークン更新", () => {
    it("許可された店舗一覧から店舗を切り替えるとonSelectStoreが実行されselectedStoreIdが更新される", async () => {
      const onSelectStore = vi.fn().mockImplementation(async (id: string) => {
        setAccessToken(`token-for-${id}`);
      });
      const onClearPreviousStoreData = vi.fn();

      const { result } = renderHook(() =>
        useStoreContext({
          stores,
          initialSelectedStoreId: "store-a1",
          onSelectStore,
          onClearPreviousStoreData,
        }),
      );

      expect(result.current.selectedStoreId).toBe("store-a1");

      await act(async () => {
        await result.current.switchStore("store-a2");
      });

      expect(onSelectStore).toHaveBeenCalledWith("store-a2");
      expect(result.current.selectedStoreId).toBe("store-a2");
      expect(onClearPreviousStoreData).toHaveBeenCalledTimes(1);
      expect(accessToken()).toBe("token-for-store-a2");
    });

    it("同じ店舗IDへの切り替えは何もしない", async () => {
      const onSelectStore = vi.fn();
      const onClearPreviousStoreData = vi.fn();

      const { result } = renderHook(() =>
        useStoreContext({
          stores,
          initialSelectedStoreId: "store-a1",
          onSelectStore,
          onClearPreviousStoreData,
        }),
      );

      await act(async () => {
        await result.current.switchStore("store-a1");
      });

      expect(onSelectStore).not.toHaveBeenCalled();
      expect(onClearPreviousStoreData).not.toHaveBeenCalled();
    });
  });

  describe("TC-105: 切替直後の旧店舗キャッシュ破棄", () => {
    it("店舗切替直後に旧店舗(A1)のデータが直ちに破棄され、A2取得完了前にA1データを返さない", async () => {
      let resolveA2: ((data: string[]) => void) | undefined;
      const fetcher = vi.fn().mockImplementation((storeId: string) => {
        if (storeId === "store-a1") {
          return Promise.resolve(["A1処方箋1", "A1処方箋2"]);
        }
        return new Promise<string[]>((res) => {
          resolveA2 = res;
        });
      });

      const { result } = renderHook(() =>
        useStoreScopedData<string[]>({ fetcher }),
      );

      // まず A1 を読み込む
      await act(async () => {
        await result.current.loadData("store-a1");
      });
      expect(result.current.data).toEqual(["A1処方箋1", "A1処方箋2"]);
      expect(result.current.activeStoreId).toBe("store-a1");

      // A2 への切り替え要求を発行（レスポンスは保留）
      act(() => {
        void result.current.loadData("store-a2");
      });

      // A2取得完了前：A1データは直ちにクリアされ、loadingがtrue
      expect(result.current.data).toBeNull();
      expect(result.current.loading).toBe(true);
      expect(result.current.activeStoreId).toBe("store-a2");

      // A2 レスポンスが完了
      await act(async () => {
        resolveA2?.(["A2処方箋1"]);
      });

      expect(result.current.data).toEqual(["A2処方箋1"]);
      expect(result.current.loading).toBe(false);
    });

    it("clearDataで明示的に即時破棄できる", async () => {
      const fetcher = vi.fn().mockResolvedValue(["A1処方箋"]);
      const { result } = renderHook(() =>
        useStoreScopedData<string[]>({ fetcher }),
      );

      await act(async () => {
        await result.current.loadData("store-a1");
      });
      expect(result.current.data).toEqual(["A1処方箋"]);

      act(() => {
        result.current.clearData();
      });

      expect(result.current.data).toBeNull();
      expect(result.current.activeStoreId).toBeNull();
    });
  });

  describe("TC-106: 旧応答遅延による上書き防止（並行競合）", () => {
    it("A1要求保留中にA2へ切り替えた場合、後から返ってきたA1の遅延応答でA2データを上書きしない", async () => {
      let resolveA1: ((data: string[]) => void) | undefined;
      let resolveA2: ((data: string[]) => void) | undefined;

      const fetcher = vi.fn().mockImplementation((storeId: string) => {
        if (storeId === "store-a1") {
          return new Promise<string[]>((res) => {
            resolveA1 = res;
          });
        }
        return new Promise<string[]>((res) => {
          resolveA2 = res;
        });
      });

      const { result } = renderHook(() =>
        useStoreScopedData<string[]>({ fetcher }),
      );

      // 1. A1 の読み込み開始（保留中）
      act(() => {
        void result.current.loadData("store-a1");
      });
      expect(result.current.loading).toBe(true);
      expect(result.current.data).toBeNull();

      // 2. A1 応答前に A2 の読み込み開始
      act(() => {
        void result.current.loadData("store-a2");
      });
      expect(result.current.loading).toBe(true);
      expect(result.current.activeStoreId).toBe("store-a2");

      // 3. 先に A2 のレスポンスが完了
      await act(async () => {
        resolveA2?.(["A2データ"]);
      });
      expect(result.current.data).toEqual(["A2データ"]);
      expect(result.current.loading).toBe(false);

      // 4. 後から遅れて A1 のレスポンスが到着
      await act(async () => {
        resolveA1?.(["遅延したA1データ"]);
      });

      // A2 の表示・キャッシュは上書きされず保護されている
      expect(result.current.data).toEqual(["A2データ"]);
      expect(result.current.activeStoreId).toBe("store-a2");
    });
  });

  describe("TC-107: 複数タブのトークン・店舗独立性", () => {
    it("sessionStorageによりタブごとにアクセストークンが独立して保持される", () => {
      // タブ1のセッション
      setAccessToken("tab1-store-a1-token");
      expect(accessToken()).toBe("tab1-store-a1-token");
      expect(sessionStorage.getItem("pharmacydomain_access_token")).toBe(
        "tab1-store-a1-token",
      );

      // ログアウトまたはクリア
      setAccessToken("");
      expect(accessToken()).toBe("");
      expect(sessionStorage.getItem("pharmacydomain_access_token")).toBeNull();
    });
  });
});
