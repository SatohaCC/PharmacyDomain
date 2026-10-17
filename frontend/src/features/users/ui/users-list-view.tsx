import { Panel } from "../../../shared/ui/layout/panel";
import {
  Table,
  TableHeader,
  IdentifierCell,
  TableCell,
} from "../../../shared/ui/data-display/table";
import {
  Title,
  Subheading,
  Paragraph,
} from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { EmptyState as Empty } from "../../../shared/ui/feedback/alert";
import type { UserList } from "../model/user";
const roles: Record<string, string> = {
  corporate_admin: "法人管理者",
  store_operator: "店舗操作者",
  store_viewer: "店舗閲覧者",
};

export function UserListView({
  data,
  corporateId,
}: {
  data: UserList;
  corporateId: string;
}) {
  const search = {};
  return (
    <Panel>
      <Title>
        <Subheading>ユーザー一覧</Subheading>
        <Link
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/users/new`}
          appearance="action"
        >
          ユーザーを招待
        </Link>
      </Title>
      <Paragraph>招待を受諾したユーザーを表示します。</Paragraph>
      {data.items.length ? (
        <Table>
          <thead>
            <tr>
              <TableHeader>本人ID</TableHeader>
              <TableHeader>権限</TableHeader>
              <TableHeader>法人権限</TableHeader>
              <TableHeader>アカウント</TableHeader>
            </tr>
          </thead>
          <tbody>
            {data.items.map((u) => (
              <tr key={u.id}>
                <IdentifierCell>{u.person_id}</IdentifierCell>
                <TableCell>{roles[u.role] || u.role}</TableCell>
                <TableCell>{u.status === "active" ? "有効" : "停止"}</TableCell>
                <TableCell>
                  {u.account_status === "active" ? "有効" : "停止"}
                </TableCell>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <Empty />
      )}
      {data.next_cursor && (
        <Link
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/users?${new URLSearchParams({ ...search, cursor: data.next_cursor! })}`}
          appearance="action"
        >
          次のページ
        </Link>
      )}
    </Panel>
  );
}
