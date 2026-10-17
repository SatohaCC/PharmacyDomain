import { createFileRoute, Link } from "@tanstack/react-router";
export const Route = createFileRoute("/admin/corporates/$corporateId/")({
  component: Overview,
});
function Overview() {
  const { corporateId } = Route.useParams();
  return (
    <section>
      <h2>法人の管理</h2>
      <p>店舗や法人を利用するユーザーを登録できます。</p>
      <div className="cards">
        <Link
          to="/admin/corporates/$corporateId/stores/new"
          params={{ corporateId }}
        >
          店舗を登録<span>店舗名・所在地・連絡先</span>
        </Link>
        <Link
          to="/admin/corporates/$corporateId/users/new"
          params={{ corporateId }}
        >
          ユーザーを招待<span>本人登録・権限・招待発行</span>
        </Link>
      </div>
    </section>
  );
}
