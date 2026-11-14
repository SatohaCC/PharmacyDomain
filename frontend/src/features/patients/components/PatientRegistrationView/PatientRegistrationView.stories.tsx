import type { Meta, StoryObj } from "@storybook/react-vite";
import { PatientRegistrationView } from "./PatientRegistrationView";

const meta = {
  title: "Features/Patients/PatientRegistrationView",
  component: PatientRegistrationView,
} satisfies Meta<typeof PatientRegistrationView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    storeId: "store-001",
    onSubmit: async () => {},
  },
};

export const Submitting: Story = {
  args: {
    storeId: "store-001",
    onSubmit: async () => {},
    isSubmitting: true,
  },
};
