import type { Meta, StoryObj } from "@storybook/react-vite";
import { CorporateLayoutView } from "./corporate-layout-view";
import { CorporateOverviewView } from "./corporates-overview-view";
const meta = {
  title: "画面/法人管理の枠",
  component: CorporateLayoutView,
  args: {
    corporate: {
      id: "example",
      name: "テスト薬局グループ",
      representative_name: "テスト 太郎",
      is_active: true,
    },
    children: <CorporateOverviewView corporateId="example" />,
  },
} satisfies Meta<typeof CorporateLayoutView>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
