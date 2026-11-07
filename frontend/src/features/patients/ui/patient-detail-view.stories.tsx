import type { Meta, StoryObj } from "@storybook/react-vite";
import { PatientDetailView } from "./patient-detail-view";
import type {
  PatientDetail,
  PatientHeading,
  PatientMedicalProfile,
} from "../model/patient";

const samplePatient: PatientDetail = {
  id: "pat-001",
  patient_number: 1001,
  corporate_id: "corp-001",
  last_name: "山田",
  first_name: "太郎",
  last_name_kana: "ヤマダ",
  first_name_kana: "タロウ",
  birth_date: "1980-05-15",
  gender: "male",
  postal_code: "100-0001",
  address: "東京都千代田区千代田1-1",
  phone_number: "090-1234-5678",
  status: "active",
  merged_into_id: null,
  status_history: [],
  profile_history: [],
};

const sampleHeading: PatientHeading = {
  patient_id: "pat-001",
  revision: 2,
  summary: "血圧高め、降圧薬アドヒアランス良好。朝食後服用を遵守。",
  notes: "大きめのカプセルは嚥下困難のため、同一成分の普通錠またはOD錠を希望。",
  updated_by_person_id: "per-001",
  updated_by_account_id: "acc-001",
  updated_at: "2026-10-15T09:30:00Z",
  history: [
    {
      revision: 1,
      summary: "初回登録。降圧薬開始。",
      notes: null,
      person_id: "per-001",
      account_id: "acc-001",
      recorded_at: "2026-09-01T10:00:00Z",
    },
    {
      revision: 2,
      summary: "血圧高め、降圧薬アドヒアランス良好。朝食後服用を遵守。",
      notes: "大きめのカプセルは嚥下困難のため、同一成分の普通錠またはOD錠を希望。",
      person_id: "per-001",
      account_id: "acc-001",
      recorded_at: "2026-10-15T09:30:00Z",
    },
  ],
};

const sampleMedicalProfile: PatientMedicalProfile = {
  id: "prof-001",
  corporate_id: "corp-001",
  patient_id: "pat-001",
  allergies: [
    {
      allergen: "ペニシリン系抗菌薬",
      reaction: "全身発疹・掻痒感",
      severity: "moderate",
      provenance: {
        source_record_id: "rec-001",
        recorded_by: "per-001",
        recorded_on: "2020-03-10",
      },
    },
  ],
  adverse_reactions: [],
  medical_conditions: [
    {
      condition_name: "本態性高血圧症",
      condition_status: "active",
      is_contraindication_target: false,
      provenance: {
        source_record_id: "rec-001",
        recorded_by: "per-001",
        recorded_on: "2019-06-01",
      },
    },
    {
      condition_name: "脂質異常症",
      condition_status: "active",
      is_contraindication_target: false,
      provenance: {
        source_record_id: "rec-001",
        recorded_by: "per-001",
        recorded_on: "2022-04-15",
      },
    },
  ],
  concurrent_medications: [
    {
      medicine_name: "アムロジピン錠 5mg",
      category: "降圧薬",
      started_on: "2026-01-10",
      ended_on: null,
      prescriber_institution: null,
      provenance: {
        source_record_id: "rec-001",
        recorded_by: "per-001",
        recorded_on: "2026-01-10",
      },
    },
  ],
  active_concurrent_medications: [
    {
      medicine_name: "アムロジピン錠 5mg",
      category: "降圧薬",
      started_on: "2026-01-10",
      ended_on: null,
      prescriber_institution: null,
      provenance: {
        source_record_id: "rec-001",
        recorded_by: "per-001",
        recorded_on: "2026-01-10",
      },
    },
  ],
  lifestyle: null,
  generic_preference: null,
  family_pharmacist: null,
};

const meta = {
  title: "Features/Patients/PatientDetailView",
  component: PatientDetailView,
} satisfies Meta<typeof PatientDetailView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    patient: samplePatient,
    heading: sampleHeading,
    medicalProfile: sampleMedicalProfile,
    storeId: "store-001",
    onUpdateHeading: async () => {},
  },
};

export const WithoutHeadingAndProfile: Story = {
  args: {
    patient: {
      ...samplePatient,
      postal_code: null,
      address: null,
      phone_number: null,
    },
    heading: null,
    medicalProfile: null,
    storeId: "store-001",
  },
};

export const MergedPatient: Story = {
  args: {
    patient: {
      ...samplePatient,
      status: "merged",
      merged_into_id: "pat-999",
    },
    heading: sampleHeading,
    medicalProfile: sampleMedicalProfile,
    storeId: "store-001",
  },
};

export const WithFetchErrors: Story = {
  args: {
    patient: samplePatient,
    heading: null,
    headingFetchError: "サーバー一時障害により取得できませんでした。",
    medicalProfile: null,
    medicalProfileFetchError: "通信エラーが発生しました。",
    storeId: "store-001",
  },
};
