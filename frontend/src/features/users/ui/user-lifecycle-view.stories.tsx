import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { UserLifecycleView } from "./user-lifecycle-view";
import type { UserLifecycleState } from "../model/lifecycle";

const activeUser: UserLifecycleState = {
  staffId: "test-staff-001",
  staffName: "テスト 太郎",
  personId: "test-person-001",
  accountId: "test-account-001",
  membershipId: "test-membership-001",
  isStaffActive: true,
  accountStatus: "active",
  membershipStatus: "active",
  storeName: "テスト薬局 本店",
};

const retiredUser: UserLifecycleState = {
  staffId: "test-staff-001",
  staffName: "テスト 太郎",
  personId: "test-person-001",
  accountId: "test-account-001",
  membershipId: "test-membership-001",
  isStaffActive: false,
  accountStatus: "suspended",
  membershipStatus: "suspended",
  storeName: "テスト薬局 本店",
  retiredOn: "2026-09-17",
};

const meta = {
  title: "画面/ユーザー退職・再開",
  component: UserLifecycleView,
  args: {
    user: activeUser,
    onRetire: fn(),
    onActivateStaff: fn(),
    onReactivateAccount: fn(),
    onReactivateMembership: fn(),
    errorMessage: null,
    isSubmitting: false,
  },
} satisfies Meta<typeof UserLifecycleView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const 在籍中: Story = {};

export const 退職拒否_在任中409: Story = {
  args: {
    user: activeUser,
    errorMessage:
      "管理薬剤師として現在任命中のため退職できません。先に任命を終了または交代してください（409 Conflict）。",
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 拒否時にも退職済みと誤表示せず、在籍中であることを確認
    await expect(canvas.getByText("在籍中")).toBeVisible();
    await expect(
      canvas.getByText(
        "管理薬剤師として現在任命中のため退職できません。先に任命を終了または交代してください（409 Conflict）。",
      ),
    ).toBeVisible();
  },
};

export const 退職処理実行: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    const retireButton = canvas.getByRole("button", {
      name: "退職処理を実行",
    });
    await userEvent.click(retireButton);
    await expect(args.onRetire).toHaveBeenCalled();
  },
};

export const 退職完了_再開画面: Story = {
  args: {
    user: retiredUser,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("退職済み")).toBeVisible();
    await expect(
      canvas.getByRole("button", { name: "スタッフを再開" }),
    ).toBeVisible();
  },
};

export const 段階的再開_スタッフ再開後: Story = {
  args: {
    user: {
      ...retiredUser,
      isStaffActive: true,
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("再開済み（在籍中）")).toBeVisible();
    await expect(
      canvas.getByRole("button", { name: "アカウントを再開" }),
    ).toBeVisible();
  },
};
