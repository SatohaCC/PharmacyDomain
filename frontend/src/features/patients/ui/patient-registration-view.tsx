import { useRef, useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  Row,
  Notice,
} from "../../../shared/ui/layout/elements";
import { TextField } from "../../../shared/ui/controls/text-field";
import { Button } from "../../../shared/ui/controls/button";
import { Link } from "../../../shared/ui/navigation/link";
import { Alert } from "../../../shared/ui/feedback/alert";
import type { RegisterPatientInput } from "../model/patient";

export interface PatientRegistrationViewProps {
  storeId: string;
  onSubmit: (input: RegisterPatientInput) => Promise<void>;
  isSubmitting?: boolean;
}

export function PatientRegistrationView({
  storeId,
  onSubmit,
  isSubmitting = false,
}: PatientRegistrationViewProps) {
  const [lastName, setLastName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastNameKana, setLastNameKana] = useState("");
  const [firstNameKana, setFirstNameKana] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const lock = useRef(false);

  const busy = isSubmitting || submitting;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || lock.current) {
      return;
    }
    if (!lastName.trim() || !firstName.trim()) {
      setError("氏名（姓・名）を入力してください。");
      return;
    }
    if (!lastNameKana.trim() || !firstNameKana.trim()) {
      setError("氏名フリガナ（セイ・メイ）を入力してください。");
      return;
    }

    lock.current = true;
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit({
        last_name: lastName.trim(),
        first_name: firstName.trim(),
        last_name_kana: lastNameKana.trim(),
        first_name_kana: firstNameKana.trim(),
        birth_date: birthDate.trim() || null,
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "患者の登録に失敗しました。",
      );
    } finally {
      lock.current = false;
      setSubmitting(false);
    }
  };

  return (
    <Panel>
      <Subheading>新規患者登録</Subheading>
      <Paragraph>
        法人の患者台帳へ患者基本情報を新規登録します。登録後、患者番号が自動採番されます。
      </Paragraph>

      <Notice>
        氏名（漢字およびカナ）は必須です。保険証やマイナンバーカード、または処方箋の記載内容と一致するように入力してください。
      </Notice>

      {error && <Alert tone="error">{error}</Alert>}

      <form onSubmit={handleSubmit} style={{ marginTop: "1rem" }}>
        <Row>
          <TextField
            name="last_name"
            label="姓（漢字）"
            required
            value={lastName}
            onValueChange={setLastName}
          />
          <TextField
            name="first_name"
            label="名（漢字）"
            required
            value={firstName}
            onValueChange={setFirstName}
          />
        </Row>

        <Row>
          <TextField
            name="last_name_kana"
            label="セイ（フリガナ）"
            required
            value={lastNameKana}
            onValueChange={setLastNameKana}
          />
          <TextField
            name="first_name_kana"
            label="メイ（フリガナ）"
            required
            value={firstNameKana}
            onValueChange={setFirstNameKana}
          />
        </Row>

        <TextField
          name="birth_date"
          label="生年月日"
          type="date"
          value={birthDate}
          onValueChange={setBirthDate}
        />

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            marginTop: "1.5rem",
          }}
        >
          <Button
            type="submit"
            variant="primary"
            disabled={busy}
            pending={busy}
          >
            {busy ? "登録中..." : "患者を登録する"}
          </Button>
          <Link href={`/stores/${encodeURIComponent(storeId)}/patients`}>
            キャンセル
          </Link>
        </div>
      </form>
    </Panel>
  );
}
