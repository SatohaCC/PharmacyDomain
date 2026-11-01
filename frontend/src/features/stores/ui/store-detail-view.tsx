import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  SectionHeading,
  Paragraph,
  Details,
  Summary,
  Row,
} from "../../../shared/ui/layout/elements";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { Badge } from "../../../shared/ui/data-display/badge";
import { Button } from "../../../shared/ui/controls/button";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
import { Alert } from "../../../shared/ui/feedback/alert";
import { type StoreDetail, STORE_STATUS_LABELS } from "../model/store";

export interface StoreDetailViewProps {
  store: StoreDetail;
  corporateId: string;
  onUpdateBasic: (names: { name: string; name_kana: string; name_romaji?: string | null; code?: string | null }) => Promise<void>;
  onUpdateAddress: (address: { postal_code: string; address: string }) => Promise<void>;
  onUpdateContact: (contact: { phone_number: string; fax_number?: string | null; email?: string | null }) => Promise<void>;
  onChangeStatus: (action: "suspend" | "resume" | "close", reason: string) => Promise<void>;
  statusMessage?: string | null;
  errorMessage?: string | null;
}

export function StoreDetailView({
  store,
  onUpdateBasic,
  onUpdateAddress,
  onUpdateContact,
  onChangeStatus,
  statusMessage,
  errorMessage,
}: StoreDetailViewProps) {
  const [basicEditing, setBasicEditing] = useState(false);
  const [addressEditing, setAddressEditing] = useState(false);
  const [contactEditing, setContactEditing] = useState(false);
  const [statusReason, setStatusReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const statusLabel = STORE_STATUS_LABELS[store.status || "active"] || "営業中";

  const handleBasicSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      await onUpdateBasic({
        name: String(fd.get("name") || ""),
        name_kana: String(fd.get("name_kana") || ""),
        name_romaji: fd.get("name_romaji") ? String(fd.get("name_romaji")) : null,
        code: fd.get("code") ? String(fd.get("code")) : null,
      });
      setBasicEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddressSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      await onUpdateAddress({
        postal_code: String(fd.get("postal_code") || ""),
        address: String(fd.get("address") || ""),
      });
      setAddressEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleContactSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      await onUpdateContact({
        phone_number: String(fd.get("phone_number") || ""),
        fax_number: fd.get("fax_number") ? String(fd.get("fax_number")) : null,
        email: fd.get("email") ? String(fd.get("email")) : null,
      });
      setContactEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStatusAction = async (action: "suspend" | "resume" | "close") => {
    setIsSubmitting(true);
    try {
      await onChangeStatus(action, statusReason || (action === "resume" ? "営業再開" : "店舗状態変更"));
      setStatusReason("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {statusMessage && <Alert tone="info">{statusMessage}</Alert>}
      {errorMessage && <Alert tone="error">{errorMessage}</Alert>}

      <Panel>
        <Subheading>{store.name} の店舗詳細</Subheading>
        <Paragraph>
          店舗コード: {store.code || "未登録"} ｜ 状態:{" "}
          <Badge>{statusLabel}</Badge>
          {store.is_community_linkage && <Badge>地域連携薬局</Badge>}
          {store.is_specialized_linkage && <Badge>専門連携薬局</Badge>}
          {store.is_health_support && <Badge>健康サポート薬局</Badge>}
        </Paragraph>
      </Panel>

      <Panel>
        <Row>
          <SectionHeading>基本情報</SectionHeading>
          <Button
            variant="secondary"
            onAction={() => setBasicEditing(!basicEditing)}
            disabled={isSubmitting}
          >
            {basicEditing ? "キャンセル" : "編集"}
          </Button>
        </Row>
        {basicEditing ? (
          <form onSubmit={(e) => void handleBasicSubmit(e)}>
            <Field name="name" label="店舗名" defaultValue={store.name} required />
            <Field name="name_kana" label="店舗名カナ" defaultValue={store.name_kana} required />
            <Field name="name_romaji" label="ローマ字名" defaultValue={store.name_romaji || ""} />
            <Field name="code" label="店舗コード" defaultValue={store.code || ""} />
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
          <Table>
            <tbody>
              <tr>
                <TableHeader>店舗名</TableHeader>
                <TableCell>{store.name}</TableCell>
                <TableHeader>カナ</TableHeader>
                <TableCell>{store.name_kana}</TableCell>
              </tr>
              <tr>
                <TableHeader>ローマ字名</TableHeader>
                <TableCell>{store.name_romaji || "未登録"}</TableCell>
                <TableHeader>店舗コード</TableHeader>
                <TableCell>{store.code || "未登録"}</TableCell>
              </tr>
              <tr>
                <TableHeader>保険薬局番号</TableHeader>
                <TableCell colSpan={3}>{store.insurance_pharmacy_number || "未登録"}</TableCell>
              </tr>
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel>
        <Row>
          <SectionHeading>所在地情報</SectionHeading>
          <Button
            variant="secondary"
            onAction={() => setAddressEditing(!addressEditing)}
            disabled={isSubmitting}
          >
            {addressEditing ? "キャンセル" : "編集"}
          </Button>
        </Row>
        {addressEditing ? (
          <form onSubmit={(e) => void handleAddressSubmit(e)}>
            <Field name="postal_code" label="郵便番号" defaultValue={store.postal_code} required />
            <Field name="address" label="住所" defaultValue={store.address} required />
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
          <Table>
            <tbody>
              <tr>
                <TableHeader>郵便番号</TableHeader>
                <TableCell>〒{store.postal_code}</TableCell>
              </tr>
              <tr>
                <TableHeader>住所</TableHeader>
                <TableCell>{store.address}</TableCell>
              </tr>
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel>
        <Row>
          <SectionHeading>連絡先情報</SectionHeading>
          <Button
            variant="secondary"
            onAction={() => setContactEditing(!contactEditing)}
            disabled={isSubmitting}
          >
            {contactEditing ? "キャンセル" : "編集"}
          </Button>
        </Row>
        {contactEditing ? (
          <form onSubmit={(e) => void handleContactSubmit(e)}>
            <Field name="phone_number" label="電話番号" defaultValue={store.phone_number} required />
            <Field name="fax_number" label="FAX番号" defaultValue={store.fax_number || ""} />
            <Field name="email" label="メールアドレス" type="email" defaultValue={store.email || ""} />
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
          <Table>
            <tbody>
              <tr>
                <TableHeader>電話番号</TableHeader>
                <TableCell>{store.phone_number}</TableCell>
                <TableHeader>FAX番号</TableHeader>
                <TableCell>{store.fax_number || "未登録"}</TableCell>
              </tr>
              <tr>
                <TableHeader>メールアドレス</TableHeader>
                <TableCell colSpan={3}>{store.email || "未登録"}</TableCell>
              </tr>
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel>
        <SectionHeading>店舗状態管理（休止・再開・閉局）</SectionHeading>
        <Paragraph>店舗の休止・営業再開・閉局の手続きを行います。</Paragraph>
        <Details>
          <Summary>状態変更アクションを開く</Summary>
          <Field
            name="status_reason"
            label="変更理由"
            value={statusReason}
            onValueChange={(val: string) => setStatusReason(val)}
          />
          <Row>
            {store.status === "active" && (
              <>
                <Button
                  variant="secondary"
                  onAction={() => void handleStatusAction("suspend")}
                  disabled={isSubmitting}
                >
                  店舗を休止する
                </Button>
                <Button
                  variant="secondary"
                  onAction={() => void handleStatusAction("close")}
                  disabled={isSubmitting}
                >
                  店舗を閉局する
                </Button>
              </>
            )}
            {store.status === "suspended" && (
              <>
                <Button
                  onAction={() => void handleStatusAction("resume")}
                  disabled={isSubmitting}
                >
                  営業を再開する
                </Button>
                <Button
                  variant="secondary"
                  onAction={() => void handleStatusAction("close")}
                  disabled={isSubmitting}
                >
                  店舗を閉局する
                </Button>
              </>
            )}
            {store.status === "closed" && (
              <Paragraph>閉局済みの店舗です。</Paragraph>
            )}
          </Row>
        </Details>
      </Panel>
    </>
  );
}
