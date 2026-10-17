import { Panel } from "../../../shared/ui/layout/panel";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { Title, Subheading } from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { EmptyState as Empty } from "../../../shared/ui/feedback/alert";
import type { Store } from "../model/store";

export function StoreListView({
  data,
  corporateId,
}: {
  data: Store[];
  corporateId: string;
}) {
  return (
    <Panel>
      <Title>
        <Subheading>店舗一覧</Subheading>
        <Link
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/stores/new`}
          appearance="action"
        >
          店舗を登録
        </Link>
      </Title>
      {data.length ? (
        <Table>
          <thead>
            <tr>
              <TableHeader>店舗名</TableHeader>
              <TableHeader>カナ</TableHeader>
              <TableHeader>店舗コード</TableHeader>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id}>
                <TableCell>{s.name}</TableCell>
                <TableCell>{s.name_kana}</TableCell>
                <TableCell>{s.code || "—"}</TableCell>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <Empty />
      )}
    </Panel>
  );
}
