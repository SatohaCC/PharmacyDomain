import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { api, result, corporationParams } from "../shared/api/client";
import { Field, Form, text, optional } from "../shared/ui/common";
export const Route = createFileRoute(
  "/admin/corporates/$corporateId/stores/new",
)({ component: NewStore });
function NewStore() {
  const { corporateId } = Route.useParams();
  const navigate = useNavigate();
  return (
    <section>
      <h2>店舗登録</h2>
      <p>開局時間・管理薬剤師はこの画面では設定されません。</p>
      <Form
        onSubmit={async (d) => {
          await result(
            api.POST("/corporates/{corporate_id}/stores", {
              params: corporationParams(corporateId),
              body: {
                name: text(d, "name"),
                name_kana: text(d, "name_kana"),
                postal_code: text(d, "postal_code"),
                address: text(d, "address"),
                phone_number: text(d, "phone_number"),
                name_romaji: optional(d, "name_romaji"),
                fax_number: optional(d, "fax_number"),
                email: optional(d, "email"),
                code: optional(d, "code"),
                insurance_pharmacy_number: optional(
                  d,
                  "insurance_pharmacy_number",
                ),
              },
            }),
          );
          await navigate({
            to: "/admin/corporates/$corporateId/stores",
            params: { corporateId },
          });
        }}
      >
        {[
          ["name", "店舗名"],
          ["name_kana", "店舗名カナ"],
          ["postal_code", "郵便番号"],
          ["address", "住所"],
          ["phone_number", "電話番号"],
        ].map(([name, label]) => (
          <Field key={name} name={name} label={label} required />
        ))}
        <details>
          <summary>任意の項目</summary>
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
        </details>
      </Form>
    </section>
  );
}
