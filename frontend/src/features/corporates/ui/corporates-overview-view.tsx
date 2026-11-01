import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  Cards,
} from "../../../shared/ui/layout/elements";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { ActionCard } from "../../../shared/ui/navigation/action-card";
import {
  type Corporate,
  CORPORATE_TYPE_LABELS,
} from "../model/corporate";

export function CorporateOverviewView({
  corporate,
}: {
  corporate: Corporate;
}) {
  const corporateTypeLabel =
    CORPORATE_TYPE_LABELS[corporate.corporate_type || "stock_company"] ||
    "株式会社";

  return (
    <>
      <Panel>
        <Subheading>法人情報</Subheading>
        <Paragraph>登記情報・税務番号・所在地・連絡先情報です。</Paragraph>
        <Table>
          <tbody>
            <tr>
              <TableHeader>法人格</TableHeader>
              <TableCell>{corporateTypeLabel}</TableCell>
              <TableHeader>法人番号</TableHeader>
              <TableCell>{corporate.corporate_number || "未登録"}</TableCell>
            </tr>
            <tr>
              <TableHeader>代表者名</TableHeader>
              <TableCell>{corporate.representative_name}</TableCell>
              <TableHeader>インボイス登録番号</TableHeader>
              <TableCell>{corporate.invoice_number || "未登録"}</TableCell>
            </tr>
            <tr>
              <TableHeader>所在地</TableHeader>
              <TableCell colSpan={3}>
                {corporate.postal_code
                  ? `〒${corporate.postal_code} ${corporate.address_line || ""}`
                  : corporate.address_line || "未登録"}
              </TableCell>
            </tr>
            <tr>
              <TableHeader>連絡先電話</TableHeader>
              <TableCell>{corporate.phone_number || "未登録"}</TableCell>
              <TableHeader>代表メール</TableHeader>
              <TableCell>{corporate.email || "未登録"}</TableCell>
            </tr>
          </tbody>
        </Table>
      </Panel>
      <Panel>
        <Subheading>運用の管理</Subheading>
        <Paragraph>店舗や法人を利用するスタッフを管理できます。</Paragraph>
        <Cards>
          <ActionCard
            href={`/admin/corporates/${encodeURIComponent(corporate.id)}/stores/new`}
            title="店舗を登録"
            description="店舗名・施設基準・所在地・連絡先"
          />
          <ActionCard
            href={`/admin/corporates/${encodeURIComponent(corporate.id)}/users/new`}
            title="スタッフ・ユーザーを登録"
            description="雇用形態・所定労働時間・資格・本人情報"
          />
        </Cards>
      </Panel>
    </>
  );
}
