import { Panel } from "../../../shared/ui/layout/panel";
import { Heading, Paragraph, Row } from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
export function CorporateRegistrationView({
  onSubmit,
}: {
  onSubmit: Submission;
}) {
  return (
    <>
      <Heading>法人登録</Heading>
      <Paragraph>最初に法人の基本情報を登録してください。</Paragraph>
      <Panel>
        <Form {...onSubmit} onSubmit={onSubmit.submit}>
          <Field name="name" label="法人名" required />
          <Row>
            <Field name="last" label="代表者の姓" required />
            <Field name="first" label="代表者の名" required />
          </Row>
        </Form>
      </Panel>
    </>
  );
}
