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
import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
import { Alert } from "../../../shared/ui/feedback/alert";
import {
  type StoreDetail,
  type BusinessWeekday,
  STORE_STATUS_LABELS,
  ORDERED_WEEKDAYS,
  WEEKDAY_LABELS,
} from "../model/store";

export interface StoreDetailViewProps {
  store: StoreDetail;
  corporateId: string;
  onUpdateBasic: (names: { name: string; name_kana: string; name_romaji?: string | null; code?: string | null }) => Promise<void>;
  onUpdateAddress: (address: { postal_code: string; address: string }) => Promise<void>;
  onUpdateContact: (contact: { phone_number: string; fax_number?: string | null; email?: string | null }) => Promise<void>;
  onUpdatePublicExpenses?: (designations: {
    public_assistance_number?: string | null;
    support_for_independence_number?: string | null;
    intractable_disease_number?: string | null;
    workers_accident_number?: string | null;
  }) => Promise<void>;
  onUpdateCertifications?: (certifications: {
    community_linkage?: { certification_number: string; valid_from: string; valid_to: string } | null;
    specialized_linkage?: { certification_number: string; disease_category: string; valid_from: string; valid_to: string } | null;
    health_support?: { notified_on: string } | null;
  }) => Promise<void>;
  onAppointSafetyManager?: (staffId: string) => Promise<void>;
  onRemoveSafetyManager?: () => Promise<void>;
  onUpdateBusinessHours?: (hours: {
    weekly: {
      weekday: BusinessWeekday;
      slots: { opens_at: string; closes_at: string }[];
    }[];
    exceptions?: {
      on: string;
      slots: { opens_at: string; closes_at: string }[];
      note?: string | null;
    }[];
  }) => Promise<void>;
  onChangeStatus: (action: "suspend" | "resume" | "close", reason: string) => Promise<void>;
  statusMessage?: string | null;
  errorMessage?: string | null;
}

export function StoreDetailView({
  store,
  onUpdateBasic,
  onUpdateAddress,
  onUpdateContact,
  onUpdatePublicExpenses,
  onUpdateCertifications,
  onAppointSafetyManager,
  onRemoveSafetyManager,
  onUpdateBusinessHours,
  onChangeStatus,
  statusMessage,
  errorMessage,
}: StoreDetailViewProps) {
  const [basicEditing, setBasicEditing] = useState(false);
  const [addressEditing, setAddressEditing] = useState(false);
  const [contactEditing, setContactEditing] = useState(false);
  const [publicExpensesEditing, setPublicExpensesEditing] = useState(false);
  const [certificationsEditing, setCertificationsEditing] = useState(false);
  const [safetyManagerIdInput, setSafetyManagerIdInput] = useState("");
  const [statusReason, setStatusReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const getInitialWeeklySchedule = () => {
    const initial: Record<
      BusinessWeekday,
      { isClosed: boolean; opensAt: string; closesAt: string }
    > = {
      monday: { isClosed: false, opensAt: "09:00", closesAt: "18:00" },
      tuesday: { isClosed: false, opensAt: "09:00", closesAt: "18:00" },
      wednesday: { isClosed: false, opensAt: "09:00", closesAt: "18:00" },
      thursday: { isClosed: false, opensAt: "09:00", closesAt: "18:00" },
      friday: { isClosed: false, opensAt: "09:00", closesAt: "18:00" },
      saturday: { isClosed: false, opensAt: "09:00", closesAt: "13:00" },
      sunday: { isClosed: true, opensAt: "09:00", closesAt: "18:00" },
    };
    if (store.business_hours?.weekly) {
      for (const day of ORDERED_WEEKDAYS) {
        const item = store.business_hours.weekly.find((w) => w.weekday === day);
        if (item) {
          const isClosed = item.slots.length === 0;
          const firstSlot = item.slots[0];
          initial[day] = {
            isClosed,
            opensAt: firstSlot ? firstSlot.opens_at.slice(0, 5) : "09:00",
            closesAt: firstSlot ? firstSlot.closes_at.slice(0, 5) : "18:00",
          };
        }
      }
    }
    return initial;
  };

  const [weeklySchedule, setWeeklySchedule] = useState(getInitialWeeklySchedule);
  const [businessHoursEditing, setBusinessHoursEditing] = useState(false);
  const [businessHoursError, setBusinessHoursError] = useState<string | null>(null);

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

  const handleBusinessHoursSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onUpdateBusinessHours) return;
    setBusinessHoursError(null);
    const weekly: {
      weekday: BusinessWeekday;
      slots: { opens_at: string; closes_at: string }[];
    }[] = ORDERED_WEEKDAYS.map((day) => {
      const item = weeklySchedule[day];
      if (item.isClosed) {
        return { weekday: day, slots: [] };
      }
      return {
        weekday: day,
        slots: [
          {
            opens_at: item.opensAt.length === 5 ? `${item.opensAt}:00` : item.opensAt,
            closes_at: item.closesAt.length === 5 ? `${item.closesAt}:00` : item.closesAt,
          },
        ],
      };
    });
    if (!weekly.some((w) => w.slots.length > 0)) {
      setBusinessHoursError("少なくとも1日の営業日（開局時間帯）を設定してください。");
      return;
    }
    setIsSubmitting(true);
    try {
      await onUpdateBusinessHours({
        weekly,
        exceptions: store.business_hours?.exceptions ?? [],
      });
      setBusinessHoursEditing(false);
    } catch (err) {
      setBusinessHoursError(
        err instanceof Error ? err.message : "開局時間の更新に失敗しました。",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePublicExpensesSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onUpdatePublicExpenses) return;
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      await onUpdatePublicExpenses({
        public_assistance_number: fd.get("public_assistance_number") ? String(fd.get("public_assistance_number")) : null,
        support_for_independence_number: fd.get("support_for_independence_number") ? String(fd.get("support_for_independence_number")) : null,
        intractable_disease_number: fd.get("intractable_disease_number") ? String(fd.get("intractable_disease_number")) : null,
        workers_accident_number: fd.get("workers_accident_number") ? String(fd.get("workers_accident_number")) : null,
      });
      setPublicExpensesEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCertificationsSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onUpdateCertifications) return;
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      const commNum = fd.get("community_linkage_number") ? String(fd.get("community_linkage_number")) : null;
      const commFrom = fd.get("community_linkage_from") ? String(fd.get("community_linkage_from")) : null;
      const commTo = fd.get("community_linkage_to") ? String(fd.get("community_linkage_to")) : null;

      const specNum = fd.get("specialized_linkage_number") ? String(fd.get("specialized_linkage_number")) : null;
      const specCat = fd.get("specialized_linkage_category") ? String(fd.get("specialized_linkage_category")) : null;
      const specFrom = fd.get("specialized_linkage_from") ? String(fd.get("specialized_linkage_from")) : null;
      const specTo = fd.get("specialized_linkage_to") ? String(fd.get("specialized_linkage_to")) : null;

      const healthNotified = fd.get("health_support_notified_on") ? String(fd.get("health_support_notified_on")) : null;

      await onUpdateCertifications({
        community_linkage: commNum && commFrom && commTo ? { certification_number: commNum, valid_from: commFrom, valid_to: commTo } : null,
        specialized_linkage: specNum && specCat && specFrom && specTo ? { certification_number: specNum, disease_category: specCat, valid_from: specFrom, valid_to: specTo } : null,
        health_support: healthNotified ? { notified_on: healthNotified } : null,
      });
      setCertificationsEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAppointSafetyManager = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onAppointSafetyManager || !safetyManagerIdInput.trim()) return;
    setIsSubmitting(true);
    try {
      await onAppointSafetyManager(safetyManagerIdInput.trim());
      setSafetyManagerIdInput("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveSafetyManager = async () => {
    if (!onRemoveSafetyManager) return;
    setIsSubmitting(true);
    try {
      await onRemoveSafetyManager();
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
        <Row>
          <div>
            <SectionHeading>開局時間（営業時間）</SectionHeading>
            <Paragraph>曜日ごとの通常開局時間および定休日の設定です。</Paragraph>
          </div>
          {onUpdateBusinessHours && (
            <Button
              variant="secondary"
              onAction={() => {
                if (!businessHoursEditing) {
                  setWeeklySchedule(getInitialWeeklySchedule());
                  setBusinessHoursError(null);
                }
                setBusinessHoursEditing(!businessHoursEditing);
              }}
              disabled={isSubmitting}
            >
              {businessHoursEditing ? "キャンセル" : "編集"}
            </Button>
          )}
        </Row>
        {businessHoursError && <Alert tone="error">{businessHoursError}</Alert>}
        {businessHoursEditing ? (
          <form onSubmit={(e) => void handleBusinessHoursSubmit(e)}>
            <Table>
              <thead>
                <tr>
                  <TableHeader>曜日</TableHeader>
                  <TableHeader>営業状態</TableHeader>
                  <TableHeader>開局時間帯（開始〜終了）</TableHeader>
                </tr>
              </thead>
              <tbody>
                {ORDERED_WEEKDAYS.map((day) => {
                  const current = weeklySchedule[day];
                  return (
                    <tr key={day}>
                      <TableCell>{WEEKDAY_LABELS[day]}</TableCell>
                      <TableCell>
                        <Checkbox
                          label="休業日"
                          isSelected={current.isClosed}
                          onChange={(checked) =>
                            setWeeklySchedule((prev) => ({
                              ...prev,
                              [day]: { ...prev[day], isClosed: checked },
                            }))
                          }
                          disabled={isSubmitting}
                        />
                      </TableCell>
                      <TableCell>
                        {!current.isClosed ? (
                          <Row>
                            <Field
                              name={`${day}_opens_at`}
                              label="開始時刻"
                              value={current.opensAt}
                              onValueChange={(val: string) =>
                                setWeeklySchedule((prev) => ({
                                  ...prev,
                                  [day]: { ...prev[day], opensAt: val },
                                }))
                              }
                              description="例: 09:00"
                              required
                            />
                            <Field
                              name={`${day}_closes_at`}
                              label="終了時刻"
                              value={current.closesAt}
                              onValueChange={(val: string) =>
                                setWeeklySchedule((prev) => ({
                                  ...prev,
                                  [day]: { ...prev[day], closesAt: val },
                                }))
                              }
                              description="例: 18:00"
                              required
                            />
                          </Row>
                        ) : (
                          <Paragraph>休業日（閉局）</Paragraph>
                        )}
                      </TableCell>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            <Row style={{ marginTop: "1rem" }}>
              <Button type="submit" disabled={isSubmitting}>
                開局時間を保存する
              </Button>
            </Row>
          </form>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <TableHeader>曜日</TableHeader>
                  <TableHeader>開局時間帯</TableHeader>
                </tr>
              </thead>
              <tbody>
                {ORDERED_WEEKDAYS.map((day) => {
                  const item = store.business_hours?.weekly?.find(
                    (w) => w.weekday === day,
                  );
                  const hasSlots = item && item.slots.length > 0;
                  return (
                    <tr key={day}>
                      <TableCell>{WEEKDAY_LABELS[day]}</TableCell>
                      <TableCell>
                        {hasSlots ? (
                          item.slots
                            .map(
                              (s) =>
                                `${s.opens_at.slice(0, 5)} 〜 ${s.closes_at.slice(0, 5)}`,
                            )
                            .join(", ")
                        ) : store.business_hours ? (
                          <Badge>休業日</Badge>
                        ) : (
                          "未登録"
                        )}
                      </TableCell>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            {store.business_hours?.exceptions && store.business_hours.exceptions.length > 0 && (
              <div style={{ marginTop: "1rem" }}>
                <SectionHeading>特例日（祝日・年末年始等）</SectionHeading>
                <Table>
                  <thead>
                    <tr>
                      <TableHeader>日付</TableHeader>
                      <TableHeader>開局時間帯</TableHeader>
                      <TableHeader>備考</TableHeader>
                    </tr>
                  </thead>
                  <tbody>
                    {store.business_hours.exceptions.map((ex) => (
                      <tr key={ex.on}>
                        <TableCell>{ex.on}</TableCell>
                        <TableCell>
                          {ex.slots.length > 0
                            ? ex.slots
                                .map(
                                  (s) =>
                                    `${s.opens_at.slice(0, 5)} 〜 ${s.closes_at.slice(0, 5)}`,
                                )
                                .join(", ")
                            : <Badge>休業日</Badge>}
                        </TableCell>
                        <TableCell>{ex.note || "-"}</TableCell>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}
          </>
        )}
      </Panel>

      <Panel>
        <Row>
          <SectionHeading>公費・指定医療機関情報</SectionHeading>
          {onUpdatePublicExpenses && (
            <Button
              variant="secondary"
              onAction={() => setPublicExpensesEditing(!publicExpensesEditing)}
              disabled={isSubmitting}
            >
              {publicExpensesEditing ? "キャンセル" : "編集"}
            </Button>
          )}
        </Row>
        {publicExpensesEditing ? (
          <form onSubmit={(e) => void handlePublicExpensesSubmit(e)}>
            <Field
              name="public_assistance_number"
              label="生活保護法指定番号"
              defaultValue={store.public_expense_designations?.public_assistance_number || ""}
            />
            <Field
              name="support_for_independence_number"
              label="自立支援医療指定番号"
              defaultValue={store.public_expense_designations?.support_for_independence_number || ""}
            />
            <Field
              name="intractable_disease_number"
              label="難病法指定番号"
              defaultValue={store.public_expense_designations?.intractable_disease_number || ""}
            />
            <Field
              name="workers_accident_number"
              label="労災保険指定番号"
              defaultValue={store.public_expense_designations?.workers_accident_number || ""}
            />
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
          <Table>
            <tbody>
              <tr>
                <TableHeader>生活保護法指定</TableHeader>
                <TableCell>{store.public_expense_designations?.public_assistance_number || "未登録"}</TableCell>
                <TableHeader>自立支援医療指定</TableHeader>
                <TableCell>{store.public_expense_designations?.support_for_independence_number || "未登録"}</TableCell>
              </tr>
              <tr>
                <TableHeader>難病法指定</TableHeader>
                <TableCell>{store.public_expense_designations?.intractable_disease_number || "未登録"}</TableCell>
                <TableHeader>労災保険指定</TableHeader>
                <TableCell>{store.public_expense_designations?.workers_accident_number || "未登録"}</TableCell>
              </tr>
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel>
        <Row>
          <SectionHeading>薬局機能認定・届出情報</SectionHeading>
          {onUpdateCertifications && (
            <Button
              variant="secondary"
              onAction={() => setCertificationsEditing(!certificationsEditing)}
              disabled={isSubmitting}
            >
              {certificationsEditing ? "キャンセル" : "編集"}
            </Button>
          )}
        </Row>
        {certificationsEditing ? (
          <form onSubmit={(e) => void handleCertificationsSubmit(e)}>
            <Paragraph>地域連携薬局認定</Paragraph>
            <Field
              name="community_linkage_number"
              label="認定番号"
              defaultValue={store.certifications?.community_linkage?.certification_number || ""}
            />
            <Field
              name="community_linkage_from"
              label="有効開始日 (YYYY-MM-DD)"
              defaultValue={store.certifications?.community_linkage?.valid_from || ""}
            />
            <Field
              name="community_linkage_to"
              label="有効満了日 (YYYY-MM-DD)"
              defaultValue={store.certifications?.community_linkage?.valid_to || ""}
            />

            <Paragraph>専門医療機関連携薬局認定</Paragraph>
            <Field
              name="specialized_linkage_number"
              label="認定番号"
              defaultValue={store.certifications?.specialized_linkage?.certification_number || ""}
            />
            <Field
              name="specialized_linkage_category"
              label="傷病区分 (例: cancer)"
              defaultValue={store.certifications?.specialized_linkage?.disease_category || ""}
            />
            <Field
              name="specialized_linkage_from"
              label="有効開始日 (YYYY-MM-DD)"
              defaultValue={store.certifications?.specialized_linkage?.valid_from || ""}
            />
            <Field
              name="specialized_linkage_to"
              label="有効満了日 (YYYY-MM-DD)"
              defaultValue={store.certifications?.specialized_linkage?.valid_to || ""}
            />

            <Paragraph>健康サポート薬局届出</Paragraph>
            <Field
              name="health_support_notified_on"
              label="届出日 (YYYY-MM-DD)"
              defaultValue={store.certifications?.health_support?.notified_on || ""}
            />
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
          <Table>
            <tbody>
              <tr>
                <TableHeader>地域連携薬局</TableHeader>
                <TableCell colSpan={3}>
                  {store.certifications?.community_linkage ? (
                    `認定番号: ${store.certifications.community_linkage.certification_number} (有効期間: ${store.certifications.community_linkage.valid_from} 〜 ${store.certifications.community_linkage.valid_to})`
                  ) : (
                    "未認定"
                  )}
                </TableCell>
              </tr>
              <tr>
                <TableHeader>専門機関連携</TableHeader>
                <TableCell colSpan={3}>
                  {store.certifications?.specialized_linkage ? (
                    `認定番号: ${store.certifications.specialized_linkage.certification_number} [区分: ${store.certifications.specialized_linkage.disease_category}] (有効期間: ${store.certifications.specialized_linkage.valid_from} 〜 ${store.certifications.specialized_linkage.valid_to})`
                  ) : (
                    "未認定"
                  )}
                </TableCell>
              </tr>
              <tr>
                <TableHeader>健康サポート</TableHeader>
                <TableCell colSpan={3}>
                  {store.certifications?.health_support ? (
                    `届出日: ${store.certifications.health_support.notified_on}`
                  ) : (
                    "未届出"
                  )}
                </TableCell>
              </tr>
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel>
        <SectionHeading>医薬品安全管理責任者</SectionHeading>
        <Paragraph>医薬品の安全使用・管理責任者の任命状況です。</Paragraph>
        <Table>
          <tbody>
            <tr>
              <TableHeader>責任者スタッフID</TableHeader>
              <TableCell>{store.safety_manager_id || "未選任"}</TableCell>
              <TableCell>
                {store.safety_manager_id && onRemoveSafetyManager && (
                  <Button
                    variant="secondary"
                    onAction={() => void handleRemoveSafetyManager()}
                    disabled={isSubmitting}
                  >
                    解任する
                  </Button>
                )}
              </TableCell>
            </tr>
          </tbody>
        </Table>
        {onAppointSafetyManager && (
          <form onSubmit={(e) => void handleAppointSafetyManager(e)} style={{ marginTop: "1rem" }}>
            <Field
              name="safety_manager_id"
              label="任命するスタッフID"
              value={safetyManagerIdInput}
              onValueChange={(val: string) => setSafetyManagerIdInput(val)}
              description="スタッフのIDを入力"
              required
            />
            <Row>
              <Button type="submit" disabled={isSubmitting || !safetyManagerIdInput.trim()}>
                医薬品安全管理責任者に任命
              </Button>
            </Row>
          </form>
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
