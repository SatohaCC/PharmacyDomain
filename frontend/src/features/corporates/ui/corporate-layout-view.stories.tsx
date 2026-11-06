import type { Meta, StoryObj } from "@storybook/react-vite";
import { CorporateLayoutView } from "./corporate-layout-view";
import { CorporateOverviewView } from "./corporates-overview-view";
const sampleCorporate = {
  id: "example",
  name: "テスト薬局グループ",
  representative_name: "テスト 太郎",
  is_active: true,
  corporate_type: "stock_company",
  corporate_number: "1234567890123",
  invoice_number: "T1234567890123",
  postal_code: "100-0001",
  address_line: "東京都千代田区千代田1-1",
  phone_number: "03-1234-5678",
  email: "info@example.com",
};

const meta = {
  title: "画面/法人管理の枠",
  component: CorporateLayoutView,
  args: {
    corporate: sampleCorporate,
    children: <CorporateOverviewView corporate={sampleCorporate} />,
  },
} satisfies Meta<typeof CorporateLayoutView>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
