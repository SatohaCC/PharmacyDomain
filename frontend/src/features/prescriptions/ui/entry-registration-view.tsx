import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Title,
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  Cards,
} from "../../../shared/ui/layout/elements";
import { TextField } from "../../../shared/ui/controls/text-field";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Button } from "../../../shared/ui/controls/button";
import { Link } from "../../../shared/ui/navigation/link";
import { Alert } from "../../../shared/ui/feedback/alert";
import {
  SAMPLE_MEDICINE_PRESETS,
  type PrescriptionEntryFormInput,
  type PrescriptionRpRowInput,
} from "../model/prescription";

export interface EntryRegistrationViewProps {
  storeId: string;
  patientId: string;
  patientName: string;
  onSubmit: (input: PrescriptionEntryFormInput) => Promise<{
    medicationHistoryCreated: boolean;
    message?: string;
  }>;
  onDone: () => void;
}

const DEFAULT_RP: PrescriptionRpRowInput = {
  category: "internal",
  quantity: 14,
  dosageName: "1日1回朝食後",
  medicineCode: SAMPLE_MEDICINE_PRESETS[0].code,
  medicineName: SAMPLE_MEDICINE_PRESETS[0].name,
  amount: "1",
  unit: SAMPLE_MEDICINE_PRESETS[0].unit,
};

export function EntryRegistrationView({
  storeId,
  patientId,
  patientName,
  onSubmit,
  onDone,
}: EntryRegistrationViewProps) {
  const today = new Date().toISOString().slice(0, 10);
  const [sourceType, setSourceType] = useState<"paper_qr" | "electronic">(
    "paper_qr",
  );
  const [issuedDate, setIssuedDate] = useState(today);
  const [documentNumber, setDocumentNumber] = useState(
    () => `RX-${today.replace(/-/g, "")}-001`,
  );
  const [institutionName, setInstitutionName] = useState("シード内科クリニック");
  const [institutionCode, setInstitutionCode] = useState("1234567");
  const [prefectureCode, setPrefectureCode] = useState("13");
  const [departmentName, setDepartmentName] = useState("内科");
  const [prescriberLastName, setPrescriberLastName] = useState("鈴木");
  const [prescriberFirstName, setPrescriberFirstName] = useState("一郎");
  const [prescriberLastNameKana, setPrescriberLastNameKana] =
    useState("スズキ");
  const [prescriberFirstNameKana, setPrescriberFirstNameKana] =
    useState("イチロウ");

  const [rps, setRps] = useState<PrescriptionRpRowInput[]>([{ ...DEFAULT_RP }]);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);

  const updateRp = (
    index: number,
    patch: Partial<PrescriptionRpRowInput>,
  ) => {
    setRps((prev) =>
      prev.map((row, idx) => (idx === index ? { ...row, ...patch } : row)),
    );
  };

  const applyPreset = (index: number, code: string) => {
    const preset = SAMPLE_MEDICINE_PRESETS.find((p) => p.code === code);
    if (!preset) return;
    updateRp(index, {
      medicineCode: preset.code,
      medicineName: preset.name,
      unit: preset.unit,
    });
  };

  const handleAddRp = () => {
    setRps((prev) => [...prev, { ...DEFAULT_RP }]);
  };

  const handleRemoveRp = (index: number) => {
    if (rps.length <= 1) return;
    setRps((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const outcome = await onSubmit({
        storeId,
        patientId,
        sourceType,
        documentNumber,
        issuedDate,
        institutionName,
        institutionCode,
        prefectureCode,
        departmentName,
        prescriberLastName,
        prescriberFirstName,
        prescriberLastNameKana,
        prescriberFirstNameKana,
        rps,
      });
      if (outcome.medicationHistoryCreated) {
        onDone();
      } else {
        setNoticeMessage(
          outcome.message ??
            "処方箋と受付イベントを登録しました。薬剤師アカウントで薬歴を開始してください。",
        );
      }
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "受付・処方の登録に失敗しました。",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const detailHref = `/stores/${encodeURIComponent(storeId)}/patients/${encodeURIComponent(patientId)}`;

  return (
    <Panel>
      <Title>
        <div>
          <Subheading>新規受付・処方登録</Subheading>
          <Paragraph>対象患者: {patientName}</Paragraph>
        </div>
        <Link href={detailHref}>患者詳細へ戻る</Link>
      </Title>

      {errorMessage ? <Alert tone="error">{errorMessage}</Alert> : null}
      {noticeMessage ? (
        <Alert tone="info">
          {noticeMessage} <Link href={detailHref}>患者詳細画面へ戻る</Link>
        </Alert>
      ) : null}

      <form
        onSubmit={(e) => void handleSubmit(e)}
        style={{ display: "grid", gap: "1.25rem", marginTop: "1rem" }}
      >
        <section>
          <SectionHeading>処方箋・医療機関情報</SectionHeading>
          <Row>
            <SelectField
              label="処方箋区分"
              name="source_type"
              value={sourceType}
              onValueChange={(value) => {
                if (value === "paper_qr" || value === "electronic") {
                  setSourceType(value);
                }
              }}
              options={[
                { value: "paper_qr", label: "紙処方箋（QR等）" },
                { value: "electronic", label: "電子処方箋" },
              ]}
            />
            <TextField
              name="issued_date"
              label="交付日"
              type="date"
              value={issuedDate}
              onValueChange={setIssuedDate}
              required
            />
            <TextField
              name="document_number"
              label="処方箋番号"
              value={documentNumber}
              onValueChange={setDocumentNumber}
              required
            />
          </Row>

          <Row>
            <TextField
              name="institution_name"
              label="医療機関名"
              value={institutionName}
              onValueChange={setInstitutionName}
              required
            />
            <TextField
              name="institution_code"
              label="医療機関コード（7桁）"
              value={institutionCode}
              onValueChange={setInstitutionCode}
              required
            />
            <TextField
              name="prefecture_code"
              label="都道府県コード（2桁）"
              value={prefectureCode}
              onValueChange={setPrefectureCode}
              required
            />
            <TextField
              name="department_name"
              label="診療科"
              value={departmentName}
              onValueChange={setDepartmentName}
              required
            />
          </Row>

          <Row>
            <TextField
              name="prescriber_last_name"
              label="処方医 姓"
              value={prescriberLastName}
              onValueChange={setPrescriberLastName}
              required
            />
            <TextField
              name="prescriber_first_name"
              label="処方医 名"
              value={prescriberFirstName}
              onValueChange={setPrescriberFirstName}
              required
            />
            <TextField
              name="prescriber_last_name_kana"
              label="処方医 セイ"
              value={prescriberLastNameKana}
              onValueChange={setPrescriberLastNameKana}
              required
            />
            <TextField
              name="prescriber_first_name_kana"
              label="処方医 メイ"
              value={prescriberFirstNameKana}
              onValueChange={setPrescriberFirstNameKana}
              required
            />
          </Row>
        </section>

        <section>
          <Row>
            <SectionHeading>処方薬明細（Rp）</SectionHeading>
            <Button variant="secondary" onAction={handleAddRp}>
              + Rp行を追加
            </Button>
          </Row>

          <Cards>
            {rps.map((rp, idx) => (
              <div
                key={idx}
                style={{
                  border: "1px solid #d7dce2",
                  borderRadius: "8px",
                  padding: "1rem",
                }}
              >
                <Row>
                  <strong>Rp {idx + 1}</strong>
                  {rps.length > 1 ? (
                    <Button
                      variant="secondary"
                      onAction={() => handleRemoveRp(idx)}
                    >
                      行を削除
                    </Button>
                  ) : null}
                </Row>

                <Row>
                  <SelectField
                    label="医薬品プリセット"
                    value={rp.medicineCode}
                    onValueChange={(value) => applyPreset(idx, value)}
                    options={SAMPLE_MEDICINE_PRESETS.map((p) => ({
                      value: p.code,
                      label: `${p.name}（YJ: ${p.code}）`,
                    }))}
                  />
                  <SelectField
                    label="剤形区分"
                    value={rp.category}
                    onValueChange={(value) => {
                      if (
                        value === "internal" ||
                        value === "prn" ||
                        value === "topical"
                      ) {
                        updateRp(idx, { category: value });
                      }
                    }}
                    options={[
                      { value: "internal", label: "内服" },
                      { value: "prn", label: "頓服" },
                      { value: "topical", label: "外用" },
                    ]}
                  />
                </Row>

                <Row>
                  <TextField
                    name={`rp_${idx}_medicine_code`}
                    label="YJコード"
                    value={rp.medicineCode}
                    onValueChange={(v) => updateRp(idx, { medicineCode: v })}
                    required
                  />
                  <TextField
                    name={`rp_${idx}_medicine_name`}
                    label="薬品名"
                    value={rp.medicineName}
                    onValueChange={(v) => updateRp(idx, { medicineName: v })}
                    required
                  />
                  <TextField
                    name={`rp_${idx}_amount`}
                    label="1日量"
                    value={rp.amount}
                    onValueChange={(v) => updateRp(idx, { amount: v })}
                    required
                  />
                  <TextField
                    name={`rp_${idx}_unit`}
                    label="単位"
                    value={rp.unit}
                    onValueChange={(v) => updateRp(idx, { unit: v })}
                    required
                  />
                </Row>

                <Row>
                  <TextField
                    name={`rp_${idx}_dosage_name`}
                    label="用法"
                    value={rp.dosageName}
                    onValueChange={(v) => updateRp(idx, { dosageName: v })}
                    required
                  />
                  <TextField
                    name={`rp_${idx}_quantity`}
                    label="日数・回数"
                    value={String(rp.quantity)}
                    onValueChange={(v) =>
                      updateRp(idx, { quantity: Math.max(1, Number(v) || 1) })
                    }
                    required
                  />
                </Row>
              </div>
            ))}
          </Cards>
        </section>

        <Row>
          <Button type="submit" disabled={submitting}>
            {submitting ? "登録中..." : "受付・処方を登録する"}
          </Button>
          <Link href={detailHref}>キャンセル</Link>
        </Row>
      </form>
    </Panel>
  );
}
