import type { Meta, StoryObj } from "@storybook/react-vite";
import { UserDetailView } from "./user-detail-view";

const meta = {
  title: "Features/Users/UserDetailView",
  component: UserDetailView,
  args: {
    corporateId: "corp-1",
    availableStores: [
      { id: "store-1", name: "テスト薬局 本店" },
      { id: "store-2", name: "テスト薬局 支店" },
    ],
    user: {
      id: "membership-1",
      account_id: "acc-1",
      person_id: "person-1",
      corporate_id: "corp-1",
      role: "store_operator",
      status: "active",
      account_status: "active",
      store_ids: ["store-1"],
      staff_id: "staff-1",
      staff: {
        id: "staff-1",
        corporate_id: "corp-1",
        last_name: "調剤",
        first_name: "花子",
        last_name_kana: "チョウザイ",
        first_name_kana: "ハナコ",
        job_title: "管理薬剤師",
        code: "STF-001",
        phone_number: "09012345678",
        email: "hanako@example.com",
        employment_type: "regular",
        weekly_contract_hours: 40,
        effective_weekly_hours: 40,
        effective_full_time_equivalent: 1.0,
        is_active: true,
        is_pharmacist: true,
      },
    },
    onUpdateRole: async () => {},
    onSuspend: async () => {},
    onReactivate: async () => {},
    onUpdateStaffNames: async () => {},
    onUpdateStaffJobTitle: async () => {},
  },
} satisfies Meta<typeof UserDetailView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const SuspendedUser: Story = {
  args: {
    user: {
      id: "membership-2",
      account_id: "acc-2",
      person_id: "person-2",
      corporate_id: "corp-1",
      role: "store_viewer",
      status: "suspended",
      account_status: "active",
      store_ids: ["store-2"],
      staff_id: null,
      staff: null,
    },
  },
};
