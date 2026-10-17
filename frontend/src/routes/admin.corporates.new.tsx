import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { api, result } from "../shared/api/client";
import { Field, Form, text } from "../shared/ui/common";
export const Route = createFileRoute("/admin/corporates/new")({
  beforeLoad: ({ context }) => {
    if (!context.actor.roles.includes("vendor_system_admin"))
      throw new Error("法人を登録する権限がありません。");
  },
  component: NewCorporate,
});
function NewCorporate() {
  const navigate = useNavigate();
  return (
    <>
      <h1>法人登録</h1>
      <p>最初に法人の基本情報を登録してください。</p>
      <section>
        <Form
          onSubmit={async (d) => {
            const data = await result(
              api.POST("/corporates", {
                body: {
                  name: text(d, "name"),
                  representative_last_name: text(d, "last"),
                  representative_first_name: text(d, "first"),
                },
              }),
            );
            await navigate({
              to: "/admin/corporates/$corporateId",
              params: { corporateId: data.id },
            });
          }}
        >
          <Field name="name" label="法人名" required />
          <div className="row">
            <Field name="last" label="代表者の姓" required />
            <Field name="first" label="代表者の名" required />
          </div>
        </Form>
      </section>
    </>
  );
}
