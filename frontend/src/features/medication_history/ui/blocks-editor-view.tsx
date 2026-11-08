import { useState, useCallback, useRef } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  SectionHeading,
  Paragraph,
  Row,
  FieldGroup,
  FieldLabel,
  TextArea,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import { Alert } from "../../../shared/ui/feedback/alert";
import { FinalizationReviewPanel } from "./finalization-review-panel";
import type { FinalizationReviewPanelProps } from "./finalization-review-panel";
import {
  type CategoryOption,
  type CurrentRecordHearingItem,
  type MedicationHistoryBlockInput,
  DEFAULT_SOAP_CATEGORIES,
} from "../model/block";

let blockKeyCounter = 0;
function createClientKey(prefix = "block"): string {
  blockKeyCounter += 1;
  return `${prefix}-${blockKeyCounter}`;
}

export interface BlockItemState extends MedicationHistoryBlockInput {
  clientKey: string;
  category_name?: string;
  category_badge_label?: string;
  updated_by_name?: string;
  updated_at?: string | null;
}

export interface BlocksEditorViewProps {
  initialBlocks?: BlockItemState[];
  hearingItems?: CurrentRecordHearingItem[];
  availableCategories?: CategoryOption[];
  isDraft?: boolean;
  onSave?: (blocks: MedicationHistoryBlockInput[]) => Promise<void>;
  onSaveHearingItems?: (items: CurrentRecordHearingItem[]) => Promise<void>;
  readOnly?: boolean;
  finalizationReview?: Omit<
    FinalizationReviewPanelProps,
    "isDraft" | "hasUnsavedChanges"
  >;
}

export function BlocksEditorView({
  initialBlocks = [],
  hearingItems = [],
  availableCategories = DEFAULT_SOAP_CATEGORIES,
  isDraft = true,
  onSave,
  onSaveHearingItems,
  readOnly = false,
  finalizationReview,
}: BlocksEditorViewProps) {
  const [blocks, setBlocks] = useState<BlockItemState[]>(() =>
    initialBlocks.map((b, idx) => ({
      ...b,
      clientKey: b.clientKey || b.id || createClientKey(`init-${idx}`),
      display_order: (idx + 1) * 10,
    })),
  );

  const [currentHearing, setCurrentHearing] =
    useState<CurrentRecordHearingItem[]>(hearingItems);
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const editRevision = useRef(0);

  const handleContentChange = (clientKey: string, newContent: string) => {
    editRevision.current += 1;
    setBlocks((prev) =>
      prev.map((b) =>
        b.clientKey === clientKey ? { ...b, content: newContent } : b,
      ),
    );
    setIsDirty(true);
    setSaveStatus(null);
  };

  const handleCategoryChange = (clientKey: string, newCategoryCode: string) => {
    editRevision.current += 1;
    const matched = availableCategories.find((c) => c.code === newCategoryCode);
    setBlocks((prev) =>
      prev.map((b) =>
        b.clientKey === clientKey
          ? {
              ...b,
              category_code: newCategoryCode,
              category_name: matched?.name ?? newCategoryCode,
              category_badge_label: matched?.badge_label ?? newCategoryCode,
            }
          : b,
      ),
    );
    setIsDirty(true);
    setSaveStatus(null);
  };

  const handleAddBlock = (categoryCode = "s") => {
    editRevision.current += 1;
    const matched = availableCategories.find((c) => c.code === categoryCode);
    const newBlock: BlockItemState = {
      clientKey: createClientKey("new"),
      category_code: categoryCode,
      category_name: matched?.name ?? categoryCode,
      category_badge_label: matched?.badge_label ?? categoryCode,
      content: "",
      display_order: (blocks.length + 1) * 10,
      source_module: "manual",
    };
    setBlocks((prev) => [...prev, newBlock]);
    setIsDirty(true);
    setSaveStatus(null);
  };

  const handleRemoveBlock = (clientKey: string) => {
    editRevision.current += 1;
    setBlocks((prev) =>
      prev
        .filter((b) => b.clientKey !== clientKey)
        .map((b, idx) => ({ ...b, display_order: (idx + 1) * 10 })),
    );
    setIsDirty(true);
    setSaveStatus(null);
  };

  const handleMoveUp = (index: number) => {
    if (index <= 0) return;
    editRevision.current += 1;
    setBlocks((prev) => {
      const copy = [...prev];
      const temp = copy[index - 1];
      copy[index - 1] = copy[index];
      copy[index] = temp;
      return copy.map((b, idx) => ({ ...b, display_order: (idx + 1) * 10 }));
    });
    setIsDirty(true);
    setSaveStatus(null);
  };

  const handleMoveDown = (index: number) => {
    if (index >= blocks.length - 1) return;
    editRevision.current += 1;
    setBlocks((prev) => {
      const copy = [...prev];
      const temp = copy[index + 1];
      copy[index + 1] = copy[index];
      copy[index] = temp;
      return copy.map((b, idx) => ({ ...b, display_order: (idx + 1) * 10 }));
    });
    setIsDirty(true);
    setSaveStatus(null);
  };

  const handleHearingValueChange = (fieldId: string, value: string) => {
    editRevision.current += 1;
    setCurrentHearing((prev) =>
      prev.map((item) =>
        item.field_id === fieldId ? { ...item, value } : item,
      ),
    );
    setIsDirty(true);
  };

  const handleSave = useCallback(async () => {
    if (!onSave || saving) return;
    const saveRevision = editRevision.current;
    setSaving(true);
    setErrorMessage(null);
    try {
      const payload: MedicationHistoryBlockInput[] = blocks.map((b, idx) => ({
        id: b.id || null,
        category_code: b.category_code,
        content: b.content,
        display_order: (idx + 1) * 10,
        source_module: b.source_module ?? "soap",
        source_id: b.source_id ?? null,
      }));
      await onSave(payload);
      if (onSaveHearingItems && currentHearing.length > 0) {
        await onSaveHearingItems(currentHearing);
      }
      if (editRevision.current === saveRevision) {
        setIsDirty(false);
        setSaveStatus("下書きを保存しました");
      } else {
        setSaveStatus("最新の変更は未保存です");
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "下書き保存中にエラーが発生しました。";
      setErrorMessage(message);
    } finally {
      setSaving(false);
    }
  }, [blocks, currentHearing, onSave, onSaveHearingItems, saving]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      void handleSave();
    }
  };

  return (
    <Panel>
      <div
        role="region"
        aria-label="薬歴記載・ブロック編集"
        onKeyDown={handleKeyDown}
        tabIndex={0}
        style={{ outline: "none" }}
      >
        <header>
          <Row>
            <SectionHeading>薬歴ブロック編集（動的区分＋文章方式）</SectionHeading>
            <Row>
              {isDraft && <Badge aria-label="記録状態">下書き</Badge>}
              {isDirty && <Badge aria-label="編集状態">編集中</Badge>}
              {saveStatus && (
                <span aria-live="polite" style={{ color: "green", fontSize: "0.875rem" }}>
                  {saveStatus}
                </span>
              )}
            </Row>
          </Row>
          <Paragraph>
            SOAP各区分および店舗カスタム区分をブロック単位で追加・編集・並び替えできます。
            Ctrl+Enter で下書き保存できます。
          </Paragraph>
        </header>

        {errorMessage && (
          <Alert tone="error">
            {errorMessage}
          </Alert>
        )}

        {/* 今回記載欄（Hearing Items） */}
        {currentHearing.length > 0 && (
          <section aria-label="今回記載欄" style={{ marginBottom: "1.5rem" }}>
            <SectionHeading>今回記載欄（ヒアリング項目）</SectionHeading>
            <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.5rem" }}>
              {currentHearing.map((h) => (
                <FieldGroup key={h.field_id}>
                  <FieldLabel>{h.label}</FieldLabel>
                  <TextArea
                    value={h.value}
                    disabled={readOnly}
                    rows={2}
                    onChange={(e) =>
                      handleHearingValueChange(h.field_id, e.target.value)
                    }
                    placeholder={`${h.label}を入力`}
                  />
                </FieldGroup>
              ))}
            </div>
          </section>
        )}

        {/* ブロックリスト */}
        <section aria-label="薬歴ブロック一覧">
          <Row>
            <SectionHeading>記載ブロック一覧（{blocks.length}件）</SectionHeading>
            {!readOnly && (
              <Row>
                {DEFAULT_SOAP_CATEGORIES.map((cat) => (
                  <Button
                    key={cat.code}
                    variant="secondary"
                    onAction={() => handleAddBlock(cat.code)}
                  >
                    ＋ {cat.badge_label}ブロック
                  </Button>
                ))}
              </Row>
            )}
          </Row>

          {blocks.length === 0 ? (
            <Paragraph>
              記載ブロックがありません。「＋ ブロック」ボタンから追加してください。
            </Paragraph>
          ) : (
            <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
              {blocks.map((block, index) => (
                <div
                  key={block.clientKey}
                  style={{
                    border: "1px solid #e0e0e0",
                    borderRadius: "8px",
                    padding: "1rem",
                    background: "#fafafa",
                  }}
                  data-testid={`block-item-${index}`}
                >
                  <Row style={{ marginBottom: "0.5rem", justifyContent: "space-between" }}>
                    <Row style={{ gap: "0.5rem", alignItems: "center" }}>
                      <Badge>{block.category_badge_label || block.category_code.toUpperCase()}</Badge>
                      <select
                        value={block.category_code}
                        disabled={readOnly}
                        aria-label={`ブロック${index + 1}の区分`}
                        onChange={(e) =>
                          handleCategoryChange(block.clientKey, e.target.value)
                        }
                        style={{
                          padding: "0.25rem 0.5rem",
                          borderRadius: "4px",
                          border: "1px solid #ccc",
                        }}
                      >
                        {availableCategories.map((c) => (
                          <option key={c.code} value={c.code}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                      {block.updated_at && (
                        <small style={{ color: "#666" }}>
                          最終更新: {new Date(block.updated_at).toLocaleTimeString()}
                          {block.updated_by_name ? ` (${block.updated_by_name})` : ""}
                        </small>
                      )}
                    </Row>

                    {!readOnly && (
                      <Row style={{ gap: "0.25rem" }}>
                        <Button
                          variant="secondary"
                          disabled={index === 0}
                          onAction={() => handleMoveUp(index)}
                          aria-label={`ブロック${index + 1}を上へ`}
                        >
                          ↑
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={index === blocks.length - 1}
                          onAction={() => handleMoveDown(index)}
                          aria-label={`ブロック${index + 1}を下へ`}
                        >
                          ↓
                        </Button>
                        <Button
                          variant="secondary"
                          onAction={() => handleRemoveBlock(block.clientKey)}
                          aria-label={`ブロック${index + 1}を削除`}
                        >
                          削除
                        </Button>
                      </Row>
                    )}
                  </Row>

                  <FieldGroup>
                    <TextArea
                      value={block.content}
                      disabled={readOnly}
                      rows={4}
                      aria-label={`${block.category_name || block.category_code}の記載本文`}
                      onChange={(e) =>
                        handleContentChange(block.clientKey, e.target.value)
                      }
                      placeholder={`${block.category_name || block.category_code} の内容を入力してください`}
                    />
                  </FieldGroup>
                </div>
              ))}
            </div>
          )}
        </section>

        {finalizationReview && (
          <FinalizationReviewPanel
            {...finalizationReview}
            isDraft={isDraft && !readOnly}
            hasUnsavedChanges={isDirty}
          />
        )}

        {/* フッターアクション */}
        {!readOnly && (
          <footer style={{ marginTop: "1.5rem" }}>
            <Row style={{ justifyContent: "flex-end", gap: "1rem" }}>
              <Button
                variant="primary"
                pending={saving}
                disabled={!onSave}
                onAction={() => void handleSave()}
              >
                下書き保存
              </Button>
            </Row>
          </footer>
        )}
      </div>
    </Panel>
  );
}
