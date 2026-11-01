import { useState } from "react";
import { UserDetailView } from "./user-detail-view";
import type { UserDetail } from "../model/user";
import type { components } from "../../../shared/api/generated/schema";
import {
  updateMembership,
  suspendUser,
  reactivateUser,
  updateStaffNames,
  updateStaffJobTitle,
  updateStaffEmployment,
  startStaffLeave,
  returnStaffFromLeave,
} from "../api/user-api";

export function UserDetailPage({
  user: initialUser,
  corporateId,
  availableStores,
  onRefresh,
}: {
  user: UserDetail;
  corporateId: string;
  availableStores: { id: string; name: string }[];
  onRefresh: () => Promise<void>;
}) {
  const [user, setUser] = useState<UserDetail>(initialUser);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const clearMessages = () => {
    setStatusMessage(null);
    setErrorMessage(null);
  };

  const handleUpdateRole = async (role: string, storeIds: string[]) => {
    clearMessages();
    try {
      await updateMembership(corporateId, user.id, {
        role: role as components["schemas"]["MembershipRole-Input"],
        store_ids: storeIds,
      });
      setUser((prev) => ({ ...prev, role, store_ids: storeIds }));
      setStatusMessage("権限および所属店舗を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "権限の更新に失敗しました。",
      );
    }
  };

  const handleSuspend = async () => {
    clearMessages();
    try {
      await suspendUser(corporateId, user.id);
      setUser((prev) => ({ ...prev, status: "suspended" }));
      setStatusMessage("アカウントの法人利用を停止しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "利用停止に失敗しました。",
      );
    }
  };

  const handleReactivate = async () => {
    clearMessages();
    try {
      await reactivateUser(corporateId, user.id);
      setUser((prev) => ({ ...prev, status: "active" }));
      setStatusMessage("アカウントの法人利用を再開しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "利用再開に失敗しました。",
      );
    }
  };

  const handleUpdateStaffNames = async (names: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  }) => {
    if (!user.staff) return;
    clearMessages();
    try {
      await updateStaffNames(corporateId, user.staff.id, names);
      setUser((prev) =>
        prev.staff
          ? {
              ...prev,
              staff: {
                ...prev.staff,
                last_name: names.last_name,
                first_name: names.first_name,
                last_name_kana: names.last_name_kana,
                first_name_kana: names.first_name_kana,
              },
            }
          : prev,
      );
      setStatusMessage("スタッフ氏名を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "氏名の更新に失敗しました。",
      );
    }
  };

  const handleUpdateStaffJobTitle = async (jobTitle: string | null) => {
    if (!user.staff) return;
    try {
      await updateStaffJobTitle(corporateId, user.staff.id, jobTitle);
      setUser((prev) =>
        prev.staff
          ? {
              ...prev,
              staff: { ...prev.staff, job_title: jobTitle },
            }
          : prev,
      );
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "役職の更新に失敗しました。",
      );
    }
  };

  const handleUpdateStaffEmployment = async (emp: {
    employment_type: string;
    weekly_contract_hours?: number | null;
  }) => {
    if (!user.staff) return;
    clearMessages();
    try {
      await updateStaffEmployment(corporateId, user.staff.id, emp);
      setUser((prev) =>
        prev.staff
          ? {
              ...prev,
              staff: {
                ...prev.staff,
                employment_type: emp.employment_type,
                weekly_contract_hours: emp.weekly_contract_hours ?? null,
              },
            }
          : prev,
      );
      setStatusMessage("労働契約内容を更新しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "労働契約の更新に失敗しました。",
      );
    }
  };

  const handleStartStaffLeave = async (leave: {
    leave_reason: string;
    left_on: string;
  }) => {
    if (!user.staff) return;
    clearMessages();
    try {
      await startStaffLeave(corporateId, user.staff.id, leave);
      setUser((prev) =>
        prev.staff
          ? {
              ...prev,
              staff: {
                ...prev.staff,
                status: "on_leave",
                leave_reason: leave.leave_reason,
              },
            }
          : prev,
      );
      setStatusMessage("スタッフの休職手続きを完了しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "休職手続きに失敗しました。",
      );
    }
  };

  const handleReturnStaffFromLeave = async () => {
    if (!user.staff) return;
    clearMessages();
    try {
      await returnStaffFromLeave(corporateId, user.staff.id);
      setUser((prev) =>
        prev.staff
          ? {
              ...prev,
              staff: {
                ...prev.staff,
                status: "active",
                leave_reason: null,
              },
            }
          : prev,
      );
      setStatusMessage("スタッフの復職手続きを完了しました。");
      await onRefresh();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "復職手続きに失敗しました。",
      );
    }
  };

  return (
    <UserDetailView
      user={user}
      corporateId={corporateId}
      availableStores={availableStores}
      onUpdateRole={handleUpdateRole}
      onSuspend={handleSuspend}
      onReactivate={handleReactivate}
      onUpdateStaffNames={user.staff ? handleUpdateStaffNames : undefined}
      onUpdateStaffJobTitle={user.staff ? handleUpdateStaffJobTitle : undefined}
      onUpdateStaffEmployment={user.staff ? handleUpdateStaffEmployment : undefined}
      onStartStaffLeave={user.staff ? handleStartStaffLeave : undefined}
      onReturnStaffFromLeave={user.staff ? handleReturnStaffFromLeave : undefined}
      statusMessage={statusMessage}
      errorMessage={errorMessage}
    />
  );
}
