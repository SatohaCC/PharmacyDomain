import { useState, type FormEvent } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Heading,
  Paragraph,
  Subheading,
  Row,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { Alert } from "../../../shared/ui/feedback/alert";
import type { CorporatePolicy } from "../model/corporate-policy";

export interface CorporatePolicyViewProps {
  initialPolicy: CorporatePolicy;
  onSave: (policy: CorporatePolicy) => Promise<void>;
}

export function CorporatePolicyView({
  initialPolicy,
  onSave,
}: CorporatePolicyViewProps) {
  const [policy, setPolicy] = useState<CorporatePolicy>(initialPolicy);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await onSave(policy);
      setSuccessMessage("法人ポリシーを保存しました。");
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "ポリシーの保存に失敗しました。",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Heading>法人ポリシー設定</Heading>
      <Paragraph>
        法人の業務ポリシーを設定します。各項目で店舗による個別上書きを許可するかどうかを制御できます。
      </Paragraph>

      <Panel>
        {successMessage && <Alert tone="info">{successMessage}</Alert>}
        {errorMessage && <Alert tone="error">{errorMessage}</Alert>}

        <form onSubmit={handleSubmit}>
          <Subheading>処方鑑査必須</Subheading>
          <Paragraph>
            有効にすると、処方鑑査で問題なしの記録が完了するまで調剤の最終合格を禁止します。
          </Paragraph>
          <Row>
            <Checkbox
              label="処方鑑査を必須とする"
              isSelected={policy.require_prescription_audit.value}
              onChange={(value) =>
                setPolicy((prev) => ({
                  ...prev,
                  require_prescription_audit: {
                    ...prev.require_prescription_audit,
                    value,
                  },
                }))
              }
            />
            <Checkbox
              label="店舗による上書きを許可"
              isSelected={policy.require_prescription_audit.overridable}
              onChange={(overridable) =>
                setPolicy((prev) => ({
                  ...prev,
                  require_prescription_audit: {
                    ...prev.require_prescription_audit,
                    overridable,
                  },
                }))
              }
            />
          </Row>

          <Subheading>自己鑑査禁止</Subheading>
          <Paragraph>
            有効にすると、調剤を実施した同一自然人による最終鑑査（合格）を禁止します。
          </Paragraph>
          <Row>
            <Checkbox
              label="同一人物による最終鑑査を禁止する"
              isSelected={policy.prohibit_self_verification.value}
              onChange={(value) =>
                setPolicy((prev) => ({
                  ...prev,
                  prohibit_self_verification: {
                    ...prev.prohibit_self_verification,
                    value,
                  },
                }))
              }
            />
            <Checkbox
              label="店舗による上書きを許可"
              isSelected={policy.prohibit_self_verification.overridable}
              onChange={(overridable) =>
                setPolicy((prev) => ({
                  ...prev,
                  prohibit_self_verification: {
                    ...prev.prohibit_self_verification,
                    overridable,
                  },
                }))
              }
            />
          </Row>

          <div style={{ marginTop: "1.5rem" }}>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "保存中..." : "ポリシーを保存"}
            </Button>
          </div>
        </form>
      </Panel>
    </>
  );
}
