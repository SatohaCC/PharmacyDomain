import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { Badge } from "../../../shared/ui/data-display/badge";
import { Title, Subheading, Row } from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { Button } from "../../../shared/ui/controls/button";
import { TextField } from "../../../shared/ui/controls/text-field";
import { EmptyState } from "../../../shared/ui/feedback/alert";
import {
  type PatientSummary,
  PATIENT_STATUS_LABELS,
  GENDER_LABELS,
} from "../model/patient";

export interface PatientListViewProps {
  patients: PatientSummary[];
  storeId: string;
  initialKeyword?: string;
  onSearch: (keyword: string) => void;
  isSearching?: boolean;
  canCreatePatient?: boolean;
}

export function PatientListView({
  patients,
  storeId,
  initialKeyword = "",
  onSearch,
  isSearching = false,
  canCreatePatient = false,
}: PatientListViewProps) {
  const [keyword, setKeyword] = useState(initialKeyword);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(keyword.trim());
  };

  const handleClear = () => {
    setKeyword("");
    onSearch("");
  };

  return (
    <Panel>
      <Title>
        <Subheading>患者一覧・検索</Subheading>
        {canCreatePatient && (
          <Link
            href={`/stores/${encodeURIComponent(storeId)}/patients/new`}
            appearance="action"
          >
            患者を新規登録
          </Link>
        )}
      </Title>

      <form onSubmit={handleSubmit} style={{ marginBlock: "1rem" }}>
        <Row>
          <TextField
            name="keyword"
            label="患者検索"
            value={keyword}
            onValueChange={setKeyword}
            description="氏名、カナ、患者番号、電話番号で検索"
          />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginTop: "0.5rem",
              marginBottom: "1rem",
            }}
          >
            <Button type="submit" variant="primary" disabled={isSearching}>
              {isSearching ? "検索中..." : "検索"}
            </Button>
            {keyword && (
              <Button variant="secondary" onAction={handleClear}>
                クリア
              </Button>
            )}
          </div>
        </Row>
      </form>

      {patients.length > 0 ? (
        <Table>
          <thead>
            <tr>
              <TableHeader>患者番号</TableHeader>
              <TableHeader>氏名</TableHeader>
              <TableHeader>フリガナ</TableHeader>
              <TableHeader>生年月日</TableHeader>
              <TableHeader>性別</TableHeader>
              <TableHeader>電話番号</TableHeader>
              <TableHeader>状態</TableHeader>
              <TableHeader>操作</TableHeader>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => {
              const patientDetailPath = `/stores/${encodeURIComponent(storeId)}/patients/${encodeURIComponent(p.id)}`;
              return (
                <tr key={p.id}>
                  <TableCell>#{p.patient_number}</TableCell>
                  <TableCell>
                    <Link href={patientDetailPath}>
                      {p.last_name} {p.first_name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {p.last_name_kana} {p.first_name_kana}
                  </TableCell>
                  <TableCell>{p.birth_date || "—"}</TableCell>
                  <TableCell>
                    {p.gender ? GENDER_LABELS[p.gender] || p.gender : "—"}
                  </TableCell>
                  <TableCell>{p.phone_number || "—"}</TableCell>
                  <TableCell>
                    <Badge>
                      {PATIENT_STATUS_LABELS[p.status] || p.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Link href={patientDetailPath}>詳細・頭書き</Link>
                  </TableCell>
                </tr>
              );
            })}
          </tbody>
        </Table>
      ) : (
        <EmptyState>該当する患者は見つかりませんでした。</EmptyState>
      )}
    </Panel>
  );
}
