import type { ReactNode } from "react";
import { AdminFrame } from "../shared/component/AdminFrame";
import { Button } from "../shared/ui/Button";
import { Link } from "../shared/ui/Link";
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
      brandHref="/admin"
      brandLabel="薬局管理"
      menuLabel="管理メニュー"
      footnote="操作範囲はログイン権限に従います"
      eyebrow="ADMIN CONSOLE"
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
