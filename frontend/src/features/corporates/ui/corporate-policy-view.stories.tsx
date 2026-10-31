import type { Meta, StoryObj } from "@storybook/react-vite";
import { CorporatePolicyView } from "./corporate-policy-view";
import type { CorporatePolicy } from "../model/corporate-policy";

const meta: Meta<typeof CorporatePolicyView> = {
  title: "Features/Corporates/CorporatePolicyView",
  component: CorporatePolicyView,
};

export default meta;
type Story = StoryObj<typeof CorporatePolicyView>;

const defaultPolicy: CorporatePolicy = {
  require_prescription_audit: {
    value: false,
    overridable: false,
  },
  prohibit_self_verification: {
    value: false,
    overridable: false,
  },
};

export const Default: Story = {
  args: {
    initialPolicy: defaultPolicy,
    onSave: async () => {},
  },
};

export const StrengthenedAndOverridable: Story = {
  args: {
    initialPolicy: {
      require_prescription_audit: {
        value: true,
        overridable: true,
      },
      prohibit_self_verification: {
        value: true,
        overridable: false,
      },
    },
    onSave: async () => {},
  },
};
