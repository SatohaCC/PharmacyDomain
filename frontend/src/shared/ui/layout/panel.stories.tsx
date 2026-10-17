import type { Meta, StoryObj } from "@storybook/react-vite";
import { Panel, Stack } from "./panel";
import { Button } from "../controls/button";
import { Paragraph } from "./elements";
const meta = {
  title: "共通UI/レイアウト/カードと余白",
  component: Panel,
  args: {
    title: "基本情報",
    children: (
      <Stack>
        <Paragraph>関連する情報をひとまとまりに表示します。</Paragraph>
        <Button variant="secondary">編集</Button>
      </Stack>
    ),
  },
} satisfies Meta<typeof Panel>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
