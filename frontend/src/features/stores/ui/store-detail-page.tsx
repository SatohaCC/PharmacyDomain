import { useState } from "react";
import { StoreDetailView } from "./store-detail-view";
import type { StoreDetail } from "../model/store";
import {
  updateStoreNames,
  updateStoreCode,
  updateStoreAddress,
  updateStoreContactInfo,
  updateStoreCertifications,
  updateStorePublicExpenseDesignations,
  appointSafetyManager,
  removeSafetyManager,
  suspendStore,
  resumeStore,
  closeStore,
} from "../api/store-api";

export function StoreDetailPage({
  store: initialStore,
  corporateId,
  onRefresh,
}: {
  store: StoreDetail;
  corporateId: string;
  onRefresh: () => Promise<void>;
}) {
  const [store, setStore] = useState<StoreDetail>(initialStore);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const clearMessages = () => {
    setStatusMessage(null);
    setErrorMessage(null);
  };

  const handleUpdateBasic = async (names: {
    name: string;
    name_kana: string;
    name_romaji?: string | null;
    code?: string | null;
  }) => {
    clearMessages();
    try {
      await updateStoreNames(corporateId, store.id, {
        name: names.name,
        name_kana: names.name_kana,
        name_romaji: names.name_romaji,
      });
      if (names.code !== store.code) {
        await updateStoreCode(corporateId, store.id, names.code || null);
      }
      setStore((prev) => ({
        ...prev,
        name: names.name,
        name_kana: names.name_kana,
        name_romaji: names.name_romaji || null,
        code: names.code || null,
      }));
      setStatusMessage("基本情報を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "基本情報の更新に失敗しました。");
    }
  };

  const handleUpdateAddress = async (addr: {
    postal_code: string;
    address: string;
  }) => {
    clearMessages();
    try {
      await updateStoreAddress(corporateId, store.id, addr);
      setStore((prev) => ({
        ...prev,
        postal_code: addr.postal_code,
        address: addr.address,
      }));
      setStatusMessage("所在地情報を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "所在地情報の更新に失敗しました。");
    }
  };

  const handleUpdateContact = async (contact: {
    phone_number: string;
    fax_number?: string | null;
    email?: string | null;
  }) => {
    clearMessages();
    try {
      await updateStoreContactInfo(corporateId, store.id, contact);
      setStore((prev) => ({
        ...prev,
        phone_number: contact.phone_number,
        fax_number: contact.fax_number || null,
        email: contact.email || null,
      }));
      setStatusMessage("連絡先情報を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "連絡先情報の更新に失敗しました。");
    }
  };

  const handleUpdatePublicExpenses = async (designations: {
    public_assistance_number?: string | null;
    support_for_independence_number?: string | null;
    intractable_disease_number?: string | null;
    workers_accident_number?: string | null;
  }) => {
    clearMessages();
    try {
      await updateStorePublicExpenseDesignations(corporateId, store.id, designations);
      setStore((prev) => ({
        ...prev,
        public_expense_designations: designations,
      }));
      setStatusMessage("公費・指定医療機関情報を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "公費指定の更新に失敗しました。",
      );
    }
  };

  const handleUpdateCertifications = async (certifications: {
    community_linkage?: { certification_number: string; valid_from: string; valid_to: string } | null;
    specialized_linkage?: { certification_number: string; disease_category: string; valid_from: string; valid_to: string } | null;
    health_support?: { notified_on: string } | null;
  }) => {
    clearMessages();
    try {
      await updateStoreCertifications(corporateId, store.id, certifications);
      setStore((prev) => ({
        ...prev,
        certifications,
      }));
      setStatusMessage("薬局機能認定・届出情報を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "認定情報の更新に失敗しました。",
      );
    }
  };

  const handleAppointSafetyManager = async (staffId: string) => {
    clearMessages();
    try {
      await appointSafetyManager(corporateId, store.id, staffId);
      setStore((prev) => ({
        ...prev,
        safety_manager_id: staffId,
      }));
      setStatusMessage("医薬品安全管理責任者を任命しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "安全管理責任者の任命に失敗しました。",
      );
    }
  };

  const handleRemoveSafetyManager = async () => {
    clearMessages();
    try {
      await removeSafetyManager(corporateId, store.id);
      setStore((prev) => ({
        ...prev,
        safety_manager_id: null,
      }));
      setStatusMessage("医薬品安全管理責任者を解任しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "安全管理責任者の解任に失敗しました。",
      );
    }
  };

  const handleChangeStatus = async (
    action: "suspend" | "resume" | "close",
    reason: string,
  ) => {
    clearMessages();
    try {
      if (action === "suspend") {
        await suspendStore(corporateId, store.id, reason);
        setStore((prev) => ({ ...prev, status: "suspended" }));
        setStatusMessage("店舗を休止しました。");
      } else if (action === "resume") {
        await resumeStore(corporateId, store.id, reason);
        setStore((prev) => ({ ...prev, status: "active" }));
        setStatusMessage("店舗の営業を再開しました。");
      } else if (action === "close") {
        await closeStore(corporateId, store.id, reason);
        setStore((prev) => ({ ...prev, status: "closed" }));
        setStatusMessage("店舗を閉局しました。");
      }
      await onRefresh();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "店舗状態の変更に失敗しました。");
    }
  };

  return (
    <StoreDetailView
      store={store}
      corporateId={corporateId}
      onUpdateBasic={handleUpdateBasic}
      onUpdateAddress={handleUpdateAddress}
      onUpdateContact={handleUpdateContact}
      onUpdatePublicExpenses={handleUpdatePublicExpenses}
      onUpdateCertifications={handleUpdateCertifications}
      onAppointSafetyManager={handleAppointSafetyManager}
      onRemoveSafetyManager={handleRemoveSafetyManager}
      onChangeStatus={handleChangeStatus}
      statusMessage={statusMessage}
      errorMessage={errorMessage}
    />
  );
}
