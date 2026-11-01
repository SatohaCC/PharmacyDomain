import { Panel } from "../../../shared/ui/layout/panel";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { Badge } from "../../../shared/ui/data-display/badge";
import { Title, Subheading } from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { EmptyState as Empty } from "../../../shared/ui/feedback/alert";
import { type Store, STORE_STATUS_LABELS } from "../model/store";

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
              <TableHeader>状態</TableHeader>
              <TableHeader>薬局機能認定</TableHeader>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id}>
                <TableCell>
                  <Link
                    href={`/admin/corporates/${encodeURIComponent(corporateId)}/stores/${encodeURIComponent(s.id)}`}
                  >
                    {s.name}
                  </Link>
                </TableCell>
                <TableCell>{s.name_kana}</TableCell>
                <TableCell>{s.code || "—"}</TableCell>
                <TableCell>
                  <Badge>
                    {STORE_STATUS_LABELS[s.status || "active"] || "営業中"}
                  </Badge>
                </TableCell>
                <TableCell>
                  {s.is_community_linkage && <Badge>地域連携</Badge>}
                  {s.is_specialized_linkage && <Badge>専門連携</Badge>}
                  {s.is_health_support && <Badge>健康サポート</Badge>}
                  {!s.is_community_linkage &&
                    !s.is_specialized_linkage &&
                    !s.is_health_support &&
                    "—"}
                </TableCell>
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
