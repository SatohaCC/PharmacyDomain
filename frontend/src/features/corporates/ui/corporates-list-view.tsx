import { SelectField } from "../../../shared/ui/controls/select-field";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import {
  Title,
  Heading,
  Paragraph,
  Row,
  Subheading,
} from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Link } from "../../../shared/ui/navigation/link";
import { EmptyState as Empty } from "../../../shared/ui/feedback/alert";
import type { CorporateList, CorporateSearch } from "../model/corporate";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";

export function CorporateListView({
  data,
  search,
  onSearch,
}: {
  data: CorporateList;
  search: CorporateSearch;
  onSearch: Submission;
}) {
  return (
    <>
      <Title>
        <div>
          <Heading>法人管理</Heading>
          <Paragraph>登録済みの法人を確認・追加します。</Paragraph>
        </div>
        <Link href={`/admin/corporates/new`} appearance="action">
          法人を登録
        </Link>
      </Title>
      <Panel>
        <Form label="検索する" {...onSearch} onSubmit={onSearch.submit}>
          <Row>
            <Field
              name="name"
              label="法人名で検索"
              defaultValue={search.name}
            />
            <SelectField
              label="状態"
              name="status"
              defaultValue={search.status}
              options={[
                { value: "", label: "すべて" },
                { value: "active", label: "有効" },
                { value: "inactive", label: "停止" },
              ]}
            />
          </Row>
        </Form>
      </Panel>
      <Panel>
        <Subheading>法人一覧</Subheading>
        {data.items.length ? (
          <Table>
            <thead>
              <tr>
                <TableHeader>法人名</TableHeader>
                <TableHeader>代表者</TableHeader>
                <TableHeader>状態</TableHeader>
                <TableHeader>操作</TableHeader>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id}>
                  <TableCell>{c.name}</TableCell>
                  <TableCell>{c.representative_name}</TableCell>
                  <TableCell>{c.is_active ? "有効" : "停止"}</TableCell>
                  <TableCell>
                    <Link
                      href={`/admin/corporates/${encodeURIComponent(c.id)}`}
                    >
                      管理する
                    </Link>
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
            href={`/admin/corporates?${new URLSearchParams({ ...search, cursor: data.next_cursor! })}`}
            appearance="action"
          >
            次のページ
          </Link>
        )}
      </Panel>
    </>
  );
}
