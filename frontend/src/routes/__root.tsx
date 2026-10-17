import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ErrorNotice } from "../shared/ui/common";
export const Route = createRootRoute({
  component: () => <Outlet />,
  notFoundComponent: () => (
    <main>
      <h1>ページが見つかりません</h1>
      <a href="/admin">管理画面へ</a>
    </main>
  ),
  errorComponent: ({ error, reset }) => (
    <main>
      <h1>画面を表示できません</h1>
      <ErrorNotice error={error} />
      <button onClick={reset}>再確認</button>
      <a href="/admin">管理画面へ</a>
    </main>
  ),
  pendingComponent: () => <main role="status">読み込み中…</main>,
});
