import { Button } from "../shared/ui/controls/button";
import { Page, Heading, Canvas } from "../shared/ui/layout/elements";
import { Providers } from "../app/providers";
import { createRootRoute, Outlet } from "@tanstack/react-router";
import { ErrorNotice } from "../app/error-notice";
export const Route = createRootRoute({
  component: () => (
    <Providers>
      <Outlet />
    </Providers>
  ),
  notFoundComponent: () => (
    <Canvas>
      <Page>
        <Heading>ページが見つかりません</Heading>
        <a href="/admin">管理画面へ</a>
      </Page>
    </Canvas>
  ),
  errorComponent: ({ error, reset }) => (
    <Canvas>
      <Page>
        <Heading>画面を表示できません</Heading>
        <ErrorNotice error={error} />
        <Button onAction={reset}>再確認</Button>
        <a href="/admin">管理画面へ</a>
      </Page>
    </Canvas>
  ),
  pendingComponent: () => (
    <Canvas>
      <Page role="status">読み込み中…</Page>
    </Canvas>
  ),
});
