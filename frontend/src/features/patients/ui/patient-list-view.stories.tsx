import type { Meta, StoryObj } from "@storybook/react-vite";
import { PatientListView } from "./patient-list-view";
import type { PatientSummary } from "../model/patient";

const samplePatients: PatientSummary[] = [
  {
    id: "pat-001",
    patient_number: 1001,
    corporate_id: "corp-001",
    last_name: "山田",
    first_name: "太郎",
    last_name_kana: "ヤマダ",
    first_name_kana: "タロウ",
    birth_date: "1980-05-15",
    gender: "male",
    phone_number: "090-1234-5678",
    status: "active",
  },
  {
    id: "pat-002",
    patient_number: 1002,
    corporate_id: "corp-001",
    last_name: "佐藤",
    first_name: "花子",
    last_name_kana: "サトウ",
    first_name_kana: "ハナコ",
    birth_date: "1992-11-20",
    gender: "female",
    phone_number: "03-9876-5432",
    status: "active",
  },
  {
    id: "pat-003",
    patient_number: 1003,
    corporate_id: "corp-001",
    last_name: "鈴木",
    first_name: "一郎",
    last_name_kana: "スズキ",
    first_name_kana: "イチロウ",
    birth_date: "1955-01-01",
    gender: "male",
    phone_number: null,
    status: "inactive",
  },
];

const meta = {
  title: "Features/Patients/PatientListView",
  component: PatientListView,
} satisfies Meta<typeof PatientListView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    patients: samplePatients,
    storeId: "store-001",
    initialKeyword: "",
    onSearch: () => {},
  },
};

export const Filtered: Story = {
  args: {
    patients: [samplePatients[0]],
    storeId: "store-001",
    initialKeyword: "山田",
    onSearch: () => {},
  },
};

export const Empty: Story = {
  args: {
    patients: [],
    storeId: "store-001",
    initialKeyword: "該当なし",
    onSearch: () => {},
  },
};
