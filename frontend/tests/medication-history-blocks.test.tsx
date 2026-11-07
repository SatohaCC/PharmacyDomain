import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BlocksEditorView } from "../src/features/medication_history/ui/blocks-editor-view";

describe("薬歴ブロック（動的区分＋文章方式）の編集・下書き保存 (Issue #91)", () => {
  it("初期ブロックと今回記載欄（ヒアリング項目）が正しく表示される", () => {
    render(
      <BlocksEditorView
        initialBlocks={[
          {
            clientKey: "b1",
            id: "block-1",
            category_code: "s",
            category_name: "S（主観的情報）",
            category_badge_label: "S",
            content: "喉の痛みを訴える。",
            display_order: 10,
            source_module: "soap",
          },
          {
            clientKey: "b2",
            id: "block-2",
            category_code: "p",
            category_name: "P（計画）",
            category_badge_label: "P",
            content: "うがい薬の併用を指導。",
            display_order: 20,
            source_module: "soap",
          },
        ]}
        hearingItems={[
          {
            field_id: "h1",
            label: "症状・体調変化",
            value: "昨日から喉の痛み",
          },
        ]}
      />,
    );

    expect(screen.getByText("喉の痛みを訴える。")).toBeDefined();
    expect(screen.getByText("うがい薬の併用を指導。")).toBeDefined();
    expect(screen.getByText("症状・体調変化")).toBeDefined();
    expect(screen.getByDisplayValue("昨日から喉の痛み")).toBeDefined();
  });

  it("ブロックを追加・編集・削除できる", async () => {
    const user = userEvent.setup();
    render(<BlocksEditorView initialBlocks={[]} />);

    // Add S block
    const addSBtn = screen.getByText("＋ Sブロック");
    await user.click(addSBtn);

    const textarea = screen.getByPlaceholderText("S（主観的情報） の内容を入力してください");
    expect(textarea).toBeDefined();

    await user.type(textarea, "花粉症の症状あり。");
    expect(screen.getByDisplayValue("花粉症の症状あり。")).toBeDefined();

    // Remove block
    const removeBtn = screen.getByRole("button", { name: "ブロック1を削除" });
    await user.click(removeBtn);

    expect(
      screen.getByText("記載ブロックがありません。「＋ ブロック」ボタンから追加してください。"),
    ).toBeDefined();
  });

  it("ブロックの並び替え（上へ・下へ）ができる", async () => {
    const user = userEvent.setup();
    render(
      <BlocksEditorView
        initialBlocks={[
          {
            clientKey: "b1",
            category_code: "s",
            category_name: "S（主観的情報）",
            content: "1番目のブロック",
            display_order: 10,
            source_module: "soap",
          },
          {
            clientKey: "b2",
            category_code: "a",
            category_name: "A（評価・判断）",
            content: "2番目のブロック",
            display_order: 20,
            source_module: "soap",
          },
        ]}
      />,
    );

    const downBtn = screen.getByRole("button", { name: "ブロック1を下へ" });
    await user.click(downBtn);

    const blockItems = screen.getAllByTestId(/block-item-/);
    expect(blockItems[0].textContent).toContain("2番目のブロック");
    expect(blockItems[1].textContent).toContain("1番目のブロック");
  });

  it("下書き保存ボタンをクリックするとonSaveが呼び出される", async () => {
    const user = userEvent.setup();
    const handleSave = vi.fn().mockResolvedValue(undefined);

    render(
      <BlocksEditorView
        initialBlocks={[
          {
            clientKey: "b1",
            category_code: "s",
            content: "保存対象のメモ",
            display_order: 10,
            source_module: "soap",
          },
        ]}
        onSave={handleSave}
      />,
    );

    const saveButton = screen.getByRole("button", { name: "下書き保存" });
    await user.click(saveButton);

    expect(handleSave).toHaveBeenCalledTimes(1);
    expect(handleSave).toHaveBeenCalledWith([
      expect.objectContaining({
        category_code: "s",
        content: "保存対象のメモ",
      }),
    ]);
    await waitFor(() => {
      expect(screen.getByText("下書きを保存しました")).toBeDefined();
    });
  });

  it("Ctrl+Enterキーで下書き保存が発火する", async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);

    render(
      <BlocksEditorView
        initialBlocks={[
          {
            clientKey: "b1",
            category_code: "s",
            content: "ショートカット保存テスト",
            display_order: 10,
            source_module: "soap",
          },
        ]}
        onSave={handleSave}
      />,
    );

    const panel = screen.getByRole("region", { name: "薬歴記載・ブロック編集" });
    fireEvent.keyDown(panel, { key: "Enter", ctrlKey: true });

    expect(handleSave).toHaveBeenCalledTimes(1);
  });
});
