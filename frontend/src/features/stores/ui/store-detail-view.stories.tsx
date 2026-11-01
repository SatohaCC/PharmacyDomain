import type { Meta, StoryObj } from "@storybook/react-vite";
import { StoreDetailView } from "./store-detail-view";

const meta = {
  title: "Features/Stores/StoreDetailView",
  component: StoreDetailView,
  args: {
    corporateId: "corp-1",
    store: {
      id: "store-1",
      corporate_id: "corp-1",
      name: "テスト薬局 本店",
      name_kana: "テストヤッキョクホンテン",
      name_romaji: "Test Pharmacy",
      postal_code: "1000001",
      address: "東京都千代田区千代田1-1",
      phone_number: "0312345678",
      fax_number: "0312345679",
      email: "store@example.com",
      code: "ST-001",
      insurance_pharmacy_number: "1234567",
      status: "active",
      is_community_linkage: true,
      is_specialized_linkage: false,
      is_health_support: true,
    },
    onUpdateBasic: async () => {},
    onUpdateAddress: async () => {},
    onUpdateContact: async () => {},
    onChangeStatus: async () => {},
  },
} satisfies Meta<typeof StoreDetailView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Suspended: Story = {
  args: {
    store: {
      id: "store-2",
      corporate_id: "corp-1",
      name: "テスト薬局 休止店",
      name_kana: "テストヤッキョクキュウシテン",
      name_romaji: null,
      postal_code: "1000002",
      address: "東京都千代田区千代田1-2",
      phone_number: "0312340000",
      fax_number: null,
      email: null,
      code: "ST-002",
      insurance_pharmacy_number: null,
      status: "suspended",
      is_community_linkage: false,
      is_specialized_linkage: false,
      is_health_support: false,
    },
  },
};

export const WithSuccessMessage: Story = {
  args: {
    statusMessage: "基本情報を更新しました。",
  },
};
