import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  Cards,
  Row,
} from "../../../shared/ui/layout/elements";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { ActionCard } from "../../../shared/ui/navigation/action-card";
import { Button } from "../../../shared/ui/controls/button";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Alert } from "../../../shared/ui/feedback/alert";
import {
  type Corporate,
  CORPORATE_TYPE_LABELS,
  CORPORATE_TYPE_OPTIONS,
} from "../model/corporate";

export function CorporateOverviewView({
  corporate,
  onUpdateDetails,
}: {
  corporate: Corporate;
  onUpdateDetails?: (details: {
    corporate_type?: string;
    corporate_number?: string | null;
    invoice_number?: string | null;
    postal_code?: string | null;
    address_line?: string | null;
    phone_number?: string | null;
    email?: string | null;
  }) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [corporateType, setCorporateType] = useState(
    corporate.corporate_type || "stock_company",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const corporateTypeLabel =
    CORPORATE_TYPE_LABELS[corporate.corporate_type || "stock_company"] ||
    "株式会社";

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onUpdateDetails) return;
    setIsSubmitting(true);
    setStatusMessage(null);
    setErrorMessage(null);
    const fd = new FormData(e.currentTarget);
    const details = {
      corporate_type: corporateType,
      corporate_number: fd.get("corporate_number") ? String(fd.get("corporate_number")) : null,
      invoice_number: fd.get("invoice_number") ? String(fd.get("invoice_number")) : null,
      postal_code: fd.get("postal_code") ? String(fd.get("postal_code")) : null,
      address_line: fd.get("address_line") ? String(fd.get("address_line")) : null,
      phone_number: fd.get("phone_number") ? String(fd.get("phone_number")) : null,
      email: fd.get("email") ? String(fd.get("email")) : null,
    };
    try {
      await onUpdateDetails(details);
      setEditing(false);
      setStatusMessage("法人詳細情報を更新しました。");
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "法人詳細情報の更新に失敗しました。",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {statusMessage && <Alert tone="info">{statusMessage}</Alert>}
      {errorMessage && <Alert tone="error">{errorMessage}</Alert>}

      <Panel>
        <Row>
          <div>
            <Subheading>法人情報</Subheading>
            <Paragraph>登記情報・税務番号・所在地・連絡先情報です。</Paragraph>
          </div>
          <Button
            variant="secondary"
            onAction={() => setEditing(!editing)}
            disabled={isSubmitting}
          >
            {editing ? "キャンセル" : "編集"}
          </Button>
        </Row>

        {editing ? (
          <form onSubmit={(e) => void handleSubmit(e)}>
            <SelectField
              name="corporate_type"
              label="法人格"
              value={corporateType}
              onValueChange={(val: string) => setCorporateType(val)}
              options={CORPORATE_TYPE_OPTIONS}
            />
            <Field
              name="corporate_number"
              label="法人番号（13桁）"
              defaultValue={corporate.corporate_number || ""}
            />
            <Field
              name="invoice_number"
              label="適格請求書発行事業者登録番号（T+13桁）"
              defaultValue={corporate.invoice_number || ""}
            />
            <Field
              name="postal_code"
              label="郵便番号"
              defaultValue={corporate.postal_code || ""}
            />
            <Field
              name="address_line"
              label="登記上所在地"
              defaultValue={corporate.address_line || ""}
            />
            <Field
              name="phone_number"
              label="代表電話番号"
              defaultValue={corporate.phone_number || ""}
            />
            <Field
              name="email"
              label="代表メールアドレス"
              type="email"
              defaultValue={corporate.email || ""}
            />
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
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
        )}
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
