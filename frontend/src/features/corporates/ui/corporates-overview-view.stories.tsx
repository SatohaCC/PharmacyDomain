import type { Meta, StoryObj } from "@storybook/react-vite";
import { CorporateOverviewView } from "./corporates-overview-view";
const meta = {
  title: "画面/法人概要",
  component: CorporateOverviewView,
  args: {
    corporate: {
      id: "example",
      name: "株式会社 メディカルファーマシー",
      representative_name: "山田 太郎",
      is_active: true,
      corporate_type: "stock_company",
      corporate_number: "1234567890123",
      invoice_number: "T1234567890123",
      postal_code: "100-0001",
      address_line: "東京都千代田区千代田1-1",
      phone_number: "03-1234-5678",
      email: "info@example.com",
    },
  },
} satisfies Meta<typeof CorporateOverviewView>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
