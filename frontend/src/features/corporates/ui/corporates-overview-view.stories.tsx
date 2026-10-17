import type { Meta, StoryObj } from "@storybook/react-vite";
import { CorporateOverviewView } from "./corporates-overview-view";
const meta = {
  title: "画面/法人概要",
  component: CorporateOverviewView,
  args: { corporateId: "example" },
} satisfies Meta<typeof CorporateOverviewView>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
