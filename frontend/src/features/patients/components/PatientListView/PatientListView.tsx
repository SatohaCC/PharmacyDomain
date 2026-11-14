import { useState } from "react";
import { Panel, Stack } from "../../../../shared/ui/Panel";
import {
  Table,
  TableHeader,
  TableRowHeader,
  TableCell,
} from "../../../../shared/ui/Table";
import { Badge } from "../../../../shared/ui/Badge";
import {
  Title,
  Subheading,
  Row,
  ActionRow,
} from "../../../../shared/ui/Elements";
import { Link } from "../../../../shared/ui/Link";
import { Button } from "../../../../shared/ui/Button";
import { TextField } from "../../../../shared/ui/TextField";
import { EmptyState } from "../../../../shared/ui/Alert";
import {
  type PatientSummary,
  PATIENT_STATUS_LABELS,
  GENDER_LABELS,
} from "../../model/patient";

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
      <Stack gap="normal">
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

        <search>
          <form onSubmit={handleSubmit}>
            <Row>
              <TextField
                name="keyword"
                label="患者検索"
                value={keyword}
                onValueChange={setKeyword}
                description="氏名、カナ、患者番号、電話番号で検索"
              />
              <ActionRow>
                <Button type="submit" variant="primary" disabled={isSearching}>
                  {isSearching ? "検索中..." : "検索"}
                </Button>
                {keyword && (
                  <Button variant="secondary" onAction={handleClear}>
                    クリア
                  </Button>
                )}
              </ActionRow>
            </Row>
          </form>
        </search>

        {patients.length > 0 ? (
          <Table ariaLabel="患者一覧">
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
                const patientName = `${p.last_name} ${p.first_name}`;
                const patientDetailPath = `/stores/${encodeURIComponent(storeId)}/patients/${encodeURIComponent(p.id)}`;
                return (
                  <tr key={p.id}>
                    <TableCell>#{p.patient_number}</TableCell>
                    <TableRowHeader>
                      <Link href={patientDetailPath}>{patientName}</Link>
                    </TableRowHeader>
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
                      <Link
                        href={patientDetailPath}
                        ariaLabel={`詳細・頭書き（${patientName}）`}
                      >
                        詳細・頭書き
                      </Link>
                    </TableCell>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        ) : (
          <EmptyState>該当する患者は見つかりませんでした。</EmptyState>
        )}
      </Stack>
    </Panel>
  );
}
