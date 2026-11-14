import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  Title,
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  Cards,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import { TextField } from "../../../shared/ui/controls/text-field";
import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { Alert } from "../../../shared/ui/feedback/alert";
import {
  DETAIL_FOOTER_ITEMS,
  orderFooterItems,
} from "../model/history-modes";

export interface StoreSettingsBasicInfo {
  id: string;
  name: string;
  code: string;
  status: string;
}

export interface MajorCategorySettingItem {
  code: string;
  name: string;
  display_order: number;
  is_enabled: boolean;
}

export interface CurrentRecordFieldSettingItem {
  id: string;
  label: string;
  category_code: string | null;
  display_order: number;
  is_enabled: boolean;
}

export interface StoreSettingsViewProps {
  store: StoreSettingsBasicInfo | null;
  categories: MajorCategorySettingItem[];
  currentRecordFields: CurrentRecordFieldSettingItem[];
  initialFooterOrder: string[];
  canEditCatalog: boolean;
  onSaveCategories: (items: MajorCategorySettingItem[]) => Promise<void>;
  onSaveCurrentRecordFields: (
    items: CurrentRecordFieldSettingItem[],
  ) => Promise<void>;
  onSaveFooterOrder: (orderIds: string[]) => void;
}

type SettingsTab = "basic" | "categories" | "current_record" | "display";

export function StoreSettingsView({
  store,
  categories,
  currentRecordFields,
  initialFooterOrder,
  canEditCatalog,
  onSaveCategories,
  onSaveCurrentRecordFields,
  onSaveFooterOrder,
}: StoreSettingsViewProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>("basic");
  const [categoryItems, setCategoryItems] =
    useState<MajorCategorySettingItem[]>(categories);
  const [newCatCode, setNewCatCode] = useState("");
  const [newCatName, setNewCatName] = useState("");

  const [fieldItems, setFieldItems] =
    useState<CurrentRecordFieldSettingItem[]>(currentRecordFields);
  const [newFieldLabel, setNewFieldLabel] = useState("");

  const [footerItems, setFooterItems] = useState(() =>
    orderFooterItems(DETAIL_FOOTER_ITEMS, initialFooterOrder),
  );

  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const runAction = async (fn: () => Promise<void>, successText: string) => {
    setSaving(true);
    setFeedback(null);
    setErrorMessage(null);
    try {
      await fn();
      setFeedback(successText);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "設定の保存に失敗しました。",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAddCategory = () => {
    const code = newCatCode.trim();
    const name = newCatName.trim();
    if (!code || !name) return;
    if (categoryItems.some((c) => c.code === code)) return;
    setCategoryItems((prev) => [
      ...prev,
      {
        code,
        name,
        display_order: (prev.length + 1) * 10,
        is_enabled: true,
      },
    ]);
    setNewCatCode("");
    setNewCatName("");
  };

  const handleAddField = () => {
    const label = newFieldLabel.trim();
    if (!label) return;
    setFieldItems((prev) => [
      ...prev,
      {
        id: `field-${Date.now()}`,
        label,
        category_code: "s",
        display_order: (prev.length + 1) * 10,
        is_enabled: true,
      },
    ]);
    setNewFieldLabel("");
  };

  const moveFooterItem = (index: number, delta: -1 | 1) => {
    const nextIndex = index + delta;
    if (nextIndex < 0 || nextIndex >= footerItems.length) return;
    const copy = [...footerItems];
    const [moved] = copy.splice(index, 1);
    copy.splice(nextIndex, 0, moved);
    setFooterItems(copy);
  };

  return (
    <Panel>
      <Title>
        <div>
          <Subheading>薬局店舗設定</Subheading>
          <Paragraph>
            {store ? `${store.name}（${store.code}）` : "店舗設定"}
          </Paragraph>
        </div>
      </Title>

      <Row>
        <Button
          variant={activeTab === "basic" ? "primary" : "secondary"}
          onAction={() => setActiveTab("basic")}
        >
          店舗基本情報
        </Button>
        <Button
          variant={activeTab === "categories" ? "primary" : "secondary"}
          onAction={() => setActiveTab("categories")}
        >
          記載区分マスタ
        </Button>
        <Button
          variant={activeTab === "current_record" ? "primary" : "secondary"}
          onAction={() => setActiveTab("current_record")}
        >
          今回記載欄設定
        </Button>
        <Button
          variant={activeTab === "display" ? "primary" : "secondary"}
          onAction={() => setActiveTab("display")}
        >
          画面表示設定（フッター順序）
        </Button>
      </Row>

      {feedback ? <Alert tone="info">{feedback}</Alert> : null}
      {errorMessage ? <Alert tone="error">{errorMessage}</Alert> : null}

      {activeTab === "basic" ? (
        <section style={{ marginTop: "1rem" }}>
          <SectionHeading>店舗基本情報</SectionHeading>
          {store ? (
            <Cards>
              <div
                style={{
                  border: "1px solid #d7dce2",
                  borderRadius: "8px",
                  padding: "1rem",
                }}
              >
                <Paragraph>店舗名: {store.name}</Paragraph>
                <Paragraph>店舗コード: {store.code}</Paragraph>
                <Row>
                  <span>状態:</span>
                  <Badge>{store.status}</Badge>
                </Row>
              </div>
            </Cards>
          ) : (
            <Paragraph>店舗情報を取得できませんでした。</Paragraph>
          )}
        </section>
      ) : null}

      {activeTab === "categories" ? (
        <section style={{ marginTop: "1rem" }}>
          <SectionHeading>薬歴記載区分マスタ（大区分）</SectionHeading>
          <Paragraph>
            患者詳細の右欄（薬歴ブロック編集）で選択できる区分を管理します。
          </Paragraph>
          <Cards>
            {categoryItems.map((cat, idx) => (
              <Row key={cat.code}>
                <Badge>{cat.code.toUpperCase()}</Badge>
                <strong>{cat.name}</strong>
                <Checkbox
                  label="有効"
                  isSelected={cat.is_enabled}
                  disabled={!canEditCatalog}
                  onChange={(checked) =>
                    setCategoryItems((prev) =>
                      prev.map((item, i) =>
                        i === idx ? { ...item, is_enabled: checked } : item,
                      ),
                    )
                  }
                />
              </Row>
            ))}
          </Cards>

          {canEditCatalog ? (
            <div style={{ marginTop: "1rem", display: "grid", gap: "0.75rem" }}>
              <Row>
                <TextField
                  name="new_category_code"
                  label="区分コード"
                  value={newCatCode}
                  onValueChange={setNewCatCode}
                />
                <TextField
                  name="new_category_name"
                  label="区分名"
                  value={newCatName}
                  onValueChange={setNewCatName}
                />
                <Button variant="secondary" onAction={handleAddCategory}>
                  区分を追加
                </Button>
              </Row>
              <div>
                <Button
                  disabled={saving}
                  onAction={() =>
                    void runAction(
                      () => onSaveCategories(categoryItems),
                      "記載区分マスタを保存しました。",
                    )
                  }
                >
                  {saving ? "保存中..." : "記載区分マスタを保存"}
                </Button>
              </div>
            </div>
          ) : (
            <Alert tone="info">
              記載区分マスタの編集には管理者権限が必要です（現在閲覧のみ）。
            </Alert>
          )}
        </section>
      ) : null}

      {activeTab === "current_record" ? (
        <section style={{ marginTop: "1rem" }}>
          <SectionHeading>今回記載欄設定</SectionHeading>
          <Paragraph>
            受付・服薬指導時の定型ヒアリング項目を店舗ごとに設定します。
          </Paragraph>
          <Cards>
            {fieldItems.map((field, idx) => (
              <Row key={field.id}>
                <strong>{field.label}</strong>
                <Checkbox
                  label="有効"
                  isSelected={field.is_enabled}
                  disabled={!canEditCatalog}
                  onChange={(checked) =>
                    setFieldItems((prev) =>
                      prev.map((item, i) =>
                        i === idx ? { ...item, is_enabled: checked } : item,
                      ),
                    )
                  }
                />
                {canEditCatalog ? (
                  <Button
                    variant="secondary"
                    onAction={() =>
                      setFieldItems((prev) => prev.filter((_, i) => i !== idx))
                    }
                  >
                    削除
                  </Button>
                ) : null}
              </Row>
            ))}
          </Cards>

          {canEditCatalog ? (
            <div style={{ marginTop: "1rem", display: "grid", gap: "0.75rem" }}>
              <Row>
                <TextField
                  name="new_field_label"
                  label="新しいヒアリング項目名"
                  value={newFieldLabel}
                  onValueChange={setNewFieldLabel}
                />
                <Button variant="secondary" onAction={handleAddField}>
                  項目を追加
                </Button>
              </Row>
              <div>
                <Button
                  disabled={saving}
                  onAction={() =>
                    void runAction(
                      () => onSaveCurrentRecordFields(fieldItems),
                      "今回記載欄設定を保存しました。",
                    )
                  }
                >
                  {saving ? "保存中..." : "今回記載欄設定を保存"}
                </Button>
              </div>
            </div>
          ) : (
            <Alert tone="info">
              今回記載欄の編集には管理者権限が必要です（現在閲覧のみ）。
            </Alert>
          )}
        </section>
      ) : null}

      {activeTab === "display" ? (
        <section style={{ marginTop: "1rem" }}>
          <SectionHeading>画面表示設定（患者詳細フッター順序）</SectionHeading>
          <Paragraph>
            患者詳細画面の下部フッターに表示される業務ボタンの並び順を設定します。
          </Paragraph>
          <Cards>
            {footerItems.map((item, idx) => (
              <Row key={item.id}>
                <span>{idx + 1}.</span>
                <strong>{item.label}</strong>
                <Button
                  variant="secondary"
                  disabled={idx === 0}
                  onAction={() => moveFooterItem(idx, -1)}
                >
                  ↑ 上へ
                </Button>
                <Button
                  variant="secondary"
                  disabled={idx === footerItems.length - 1}
                  onAction={() => moveFooterItem(idx, 1)}
                >
                  ↓ 下へ
                </Button>
              </Row>
            ))}
          </Cards>
          <Row>
            <Button
              onAction={() => {
                onSaveFooterOrder(footerItems.map((i) => i.id));
                setFeedback("フッター表示順を保存しました。");
              }}
            >
              表示順を保存
            </Button>
            <Button
              variant="secondary"
              onAction={() => {
                setFooterItems([...DETAIL_FOOTER_ITEMS]);
                onSaveFooterOrder(DETAIL_FOOTER_ITEMS.map((i) => i.id));
                setFeedback("既定の並び順に戻しました。");
              }}
            >
              既定順に戻す
            </Button>
          </Row>
        </section>
      ) : null}
    </Panel>
  );
}
