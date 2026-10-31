import { useState, type FormEvent } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Heading,
  Paragraph,
  Subheading,
  Row,
  Paragraph as Description,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Alert } from "../../../shared/ui/feedback/alert";
import { Badge } from "../../../shared/ui/data-display/badge";
import type { EffectivePolicy, StorePolicy } from "../model/store-policy";

export interface CorporatePolicySnapshot {
  require_prescription_audit: {
    value: boolean;
    overridable: boolean;
  };
  prohibit_self_verification: {
    value: boolean;
    overridable: boolean;
  };
}

export interface StorePolicyViewProps {
  corporatePolicy: CorporatePolicySnapshot;
  initialStorePolicy: StorePolicy;
  effectivePolicy: EffectivePolicy;
  onSave: (policy: StorePolicy) => Promise<void>;
}

export function StorePolicyView({
  corporatePolicy,
  initialStorePolicy,
  effectivePolicy,
  onSave,
}: StorePolicyViewProps) {
  const [storePolicy, setStorePolicy] = useState<StorePolicy>(initialStorePolicy);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await onSave(storePolicy);
      setSuccessMessage("店舗ポリシーを保存しました。");
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "店舗ポリシーの保存に失敗しました。",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const toSelectValue = (val: boolean | null): string => {
    if (val === null) return "inherit";
    return val ? "true" : "false";
  };

  const fromSelectValue = (val: string): boolean | null => {
    if (val === "inherit") return null;
    return val === "true";
  };

  const overrideOptions = [
    { value: "inherit", label: "法人設定に従う（上書きなし）" },
    { value: "true", label: "有効に上書き" },
    { value: "false", label: "無効に上書き" },
  ];

  return (
    <>
      <Heading>店舗ポリシー設定</Heading>
      <Paragraph>
        店舗ごとの調剤業務ポリシーを設定します。法人が上書きを許可している項目のみ個別に上書きできます。
      </Paragraph>

      <Panel>
        {successMessage && <Alert tone="info">{successMessage}</Alert>}
        {errorMessage && <Alert tone="error">{errorMessage}</Alert>}

        <form onSubmit={handleSubmit}>
          {/* 1. 処方鑑査必須 */}
          <Subheading>処方鑑査必須</Subheading>
          <Description>
            現在実効値:{" "}
            <strong>
              {effectivePolicy.require_prescription_audit.value ? "必須" : "任意"}
            </strong>{" "}
            <Badge>
              {effectivePolicy.require_prescription_audit.source === "corporate"
                ? "法人設定"
                : "店舗上書き"}
            </Badge>
          </Description>
          <Description>
            法人設定: {corporatePolicy.require_prescription_audit.value ? "有効" : "無効"} /
            店舗上書き:{" "}
            {corporatePolicy.require_prescription_audit.overridable
              ? "許可"
              : "禁止（変更不可）"}
          </Description>

          {!corporatePolicy.require_prescription_audit.overridable &&
            storePolicy.require_prescription_audit !== null && (
              <Alert tone="info">
                ※ 法人により上書きが禁止されているため、法人設定が適用されます。以前保存された店舗設定（
                {storePolicy.require_prescription_audit ? "有効" : "無効"}
                ）は保持されており、法人が上書きを再許可した際に自動で復活します。
              </Alert>
            )}

          <SelectField
            label="店舗の個別設定"
            options={overrideOptions}
            value={toSelectValue(storePolicy.require_prescription_audit)}
            disabled={!corporatePolicy.require_prescription_audit.overridable}
            onValueChange={(val) =>
              setStorePolicy((prev) => ({
                ...prev,
                require_prescription_audit: fromSelectValue(val),
              }))
            }
          />

          {/* 2. 自己鑑査禁止 */}
          <Subheading>自己鑑査禁止</Subheading>
          <Description>
            現在実効値:{" "}
            <strong>
              {effectivePolicy.prohibit_self_verification.value ? "禁止" : "許容"}
            </strong>{" "}
            <Badge>
              {effectivePolicy.prohibit_self_verification.source === "corporate"
                ? "法人設定"
                : "店舗上書き"}
            </Badge>
          </Description>
          <Description>
            法人設定: {corporatePolicy.prohibit_self_verification.value ? "禁止" : "許容"} /
            店舗上書き:{" "}
            {corporatePolicy.prohibit_self_verification.overridable
              ? "許可"
              : "禁止（変更不可）"}
          </Description>

          {!corporatePolicy.prohibit_self_verification.overridable &&
            storePolicy.prohibit_self_verification !== null && (
              <Alert tone="info">
                ※ 法人により上書きが禁止されているため、法人設定が適用されます。以前保存された店舗設定（
                {storePolicy.prohibit_self_verification ? "禁止" : "許容"}
                ）は保持されており、法人が上書きを再許可した際に自動で復活します。
              </Alert>
            )}

          <SelectField
            label="店舗の個別設定"
            options={overrideOptions}
            value={toSelectValue(storePolicy.prohibit_self_verification)}
            disabled={!corporatePolicy.prohibit_self_verification.overridable}
            onValueChange={(val) =>
              setStorePolicy((prev) => ({
                ...prev,
                prohibit_self_verification: fromSelectValue(val),
              }))
            }
          />

          <Row>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "保存中..." : "店舗ポリシーを保存"}
            </Button>
          </Row>
        </form>
      </Panel>
    </>
  );
}
