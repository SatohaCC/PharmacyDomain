import type { Meta, StoryObj } from "@storybook/react-vite";
import { Table, TableHeader, TableCell } from "./table";
import { Badge } from "./badge";
function Example() {
  return (
    <Table>
      <caption>表示の例</caption>
      <thead>
        <tr>
          <TableHeader>名称</TableHeader>
          <TableHeader>状態</TableHeader>
        </tr>
      </thead>
      <tbody>
        <tr>
          <TableCell>テスト</TableCell>
          <TableCell>
            <Badge>有効</Badge>
          </TableCell>
        </tr>
      </tbody>
    </Table>
  );
}
const meta = {
  title: "共通UI/データ表示/一覧と状態",
  component: Example,
} satisfies Meta<typeof Example>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
