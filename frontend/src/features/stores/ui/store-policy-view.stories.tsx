import type { Meta, StoryObj } from "@storybook/react-vite";
import { StorePolicyView } from "./store-policy-view";

const meta: Meta<typeof StorePolicyView> = {
  title: "Features/Stores/StorePolicyView",
  component: StorePolicyView,
};

export default meta;
type Story = StoryObj<typeof StorePolicyView>;

export const Default: Story = {
  args: {
    corporatePolicy: {
      require_prescription_audit: { value: false, overridable: true },
      prohibit_self_verification: { value: false, overridable: false },
    },
    initialStorePolicy: {
      require_prescription_audit: null,
      prohibit_self_verification: null,
    },
    effectivePolicy: {
      require_prescription_audit: { value: false, source: "corporate" },
      prohibit_self_verification: { value: false, source: "corporate" },
    },
    onSave: async () => {},
  },
};

export const OverriddenAndRetained: Story = {
  args: {
    corporatePolicy: {
      require_prescription_audit: { value: false, overridable: false },
      prohibit_self_verification: { value: true, overridable: true },
    },
    initialStorePolicy: {
      require_prescription_audit: true, // 以前の上書き値が保持されている
      prohibit_self_verification: false,
    },
    effectivePolicy: {
      require_prescription_audit: { value: false, source: "corporate" },
      prohibit_self_verification: { value: false, source: "store" },
    },
    onSave: async () => {},
  },
};

export const ConflictError: Story = {
  args: {
    corporatePolicy: {
      require_prescription_audit: { value: false, overridable: false },
      prohibit_self_verification: { value: false, overridable: false },
    },
    initialStorePolicy: {
      require_prescription_audit: null,
      prohibit_self_verification: null,
    },
    effectivePolicy: {
      require_prescription_audit: { value: false, source: "corporate" },
      prohibit_self_verification: { value: false, source: "corporate" },
    },
    onSave: async () => {
      throw new Error(
        "法人が上書きを禁止している項目に個別設定を指定することはできません。(409 Conflict)",
      );
    },
  },
};
