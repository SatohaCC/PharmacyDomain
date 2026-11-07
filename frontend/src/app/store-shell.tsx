import type { ReactNode } from "react";
import { StoreFrame } from "../shared/ui/layout/store-frame";
import { Button } from "../shared/ui/controls/button";
import { Link } from "../shared/ui/navigation/link";
import { logout } from "../features/auth/api/session";

export interface StoreShellProps {
  storeId: string;
  storeName?: string;
  actor: {
    roles: string[];
    corporate_id: string | null;
    selected_store_id?: string | null;
  };
  storeSelector?: ReactNode;
  children: ReactNode;
}

export function StoreShell({
  storeId,
  storeName,
  actor,
  storeSelector,
  children,
}: StoreShellProps) {
  const getRoleLabel = () => {
    if (actor.roles.includes("vendor_system_admin")) return "システム管理者";
    if (actor.roles.includes("corporate_admin")) return "法人管理者";
    if (actor.roles.includes("store_operator")) return "店舗スタッフ (操作)";
    if (actor.roles.includes("store_viewer")) return "店舗スタッフ (閲覧)";
    return "スタッフ";
  };

  const isAdmin = actor.roles.some(
    (r) => r === "corporate_admin" || r === "vendor_system_admin",
  );

  return (
    <StoreFrame
      storeName={storeName || "調剤現場業務"}
      identity={getRoleLabel()}
      navigation={
        <>
          {storeSelector}
          <Link href={`/stores/${encodeURIComponent(storeId)}/patients`}>
            患者一覧・検索
          </Link>
          {isAdmin && (
            <Link href={`/stores/${encodeURIComponent(storeId)}/patients/new`}>
              新規患者登録
            </Link>
          )}
          {isAdmin && <Link href="/admin">管理画面へ</Link>}
          <Button variant="secondary" onAction={() => void logout()}>
            ログアウト
          </Button>
        </>
      }
    >
      <nav aria-label="パンくず" style={{ marginBottom: "1rem" }}>
        <Link href={`/stores/${encodeURIComponent(storeId)}/patients`}>
          業務ホーム
        </Link>
      </nav>
      {children}
    </StoreFrame>
  );
}
