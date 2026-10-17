import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  Details,
  Summary,
} from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
export function StoreRegistrationView({ onSubmit }: { onSubmit: Submission }) {
  return (
    <Panel>
      <Subheading>店舗登録</Subheading>
      <Paragraph>開局時間・管理薬剤師はこの画面では設定されません。</Paragraph>
      <Form {...onSubmit} onSubmit={onSubmit.submit}>
        {[
          ["name", "店舗名"],
          ["name_kana", "店舗名カナ"],
          ["postal_code", "郵便番号"],
          ["address", "住所"],
          ["phone_number", "電話番号"],
        ].map(([name, label]) => (
          <Field key={name} name={name} label={label} required />
        ))}
        <Details>
          <Summary>任意の項目</Summary>
          {[
            ["name_romaji", "ローマ字名"],
            ["fax_number", "FAX"],
            ["email", "メール"],
            ["code", "店舗コード"],
            ["insurance_pharmacy_number", "保険薬局番号"],
          ].map(([name, label]) => (
            <Field
              key={name}
              name={name}
              label={label}
              type={name === "email" ? "email" : "text"}
            />
          ))}
        </Details>
      </Form>
    </Panel>
  );
}
