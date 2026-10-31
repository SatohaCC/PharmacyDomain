import type { ReactNode } from "react";
import { AdminFrame } from "../shared/ui/layout/elements";
import { Button } from "../shared/ui/controls/button";
import { Link } from "../shared/ui/navigation/link";
import { logout } from "../features/auth/api/session";

export interface AdminShellProps {
  actor: {
    roles: string[];
    corporate_id: string | null;
    selected_store_id?: string | null;
  };
  storeSelector?: ReactNode;
  children: ReactNode;
}

export function AdminShell({
  actor,
  storeSelector,
  children,
}: AdminShellProps) {
  const corporatePath = actor.corporate_id
    ? `/admin/corporates/${encodeURIComponent(actor.corporate_id)}`
    : "/admin/corporates";
  return (
    <AdminFrame
      identity={
        actor.roles.includes("vendor_system_admin")
          ? "システム管理者"
          : "法人管理者"
      }
      navigation={
        <>
          {storeSelector}
          {actor.roles.includes("vendor_system_admin") ? (
            <Link href="/admin/corporates">法人管理</Link>
          ) : (
            <Link href={corporatePath}>自法人の管理</Link>
          )}
          <Button variant="secondary" onAction={() => void logout()}>
            ログアウト
          </Button>
        </>
      }
    >
      <nav aria-label="パンくず">
        <Link href={corporatePath}>管理ホーム</Link>
      </nav>
      {children}
    </AdminFrame>
  );
}
