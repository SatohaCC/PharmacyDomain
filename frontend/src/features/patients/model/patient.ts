export type PatientStatus = "active" | "inactive" | "merged";

export const PATIENT_STATUS_LABELS: Record<string, string> = {
  active: "有効",
  inactive: "無効",
  merged: "統合済み",
};

export const GENDER_LABELS: Record<string, string> = {
  male: "男性",
  female: "女性",
  other: "その他",
  unknown: "不明",
};

export interface PatientSummary {
  id: string;
  patient_number: number;
  corporate_id: string;
  last_name: string;
  first_name: string;
  last_name_kana: string;
  first_name_kana: string;
  birth_date: string | null;
  gender?: string | null;
  phone_number?: string | null;
  status: string;
}

export interface PatientDetail {
  id: string;
  patient_number: number;
  corporate_id: string;
  last_name: string;
  first_name: string;
  last_name_kana: string;
  first_name_kana: string;
  birth_date: string | null;
  gender?: string | null;
  postal_code?: string | null;
  address?: string | null;
  phone_number?: string | null;
  status: string;
  merged_into_id?: string | null;
  status_history: Array<{
    before: string;
    after: string;
    reason: string;
    person_id: string;
    account_id: string;
    recorded_at: string;
    merged_into_id?: string | null;
  }>;
  profile_history: Array<{
    recorded_at: string;
    changed_fields: string[];
    source?: string;
    reception_id?: string | null;
    store_id?: string | null;
    external_patient_id?: string | null;
  }>;
}

export interface PatientHeadingRevision {
  revision: number;
  summary: string | null;
  notes: string | null;
  person_id: string;
  account_id: string;
  recorded_at: string;
}

export interface PatientHeading {
  patient_id: string;
  revision: number;
  summary: string | null;
  notes: string | null;
  updated_by_person_id: string | null;
  updated_by_account_id: string | null;
  updated_at: string | null;
  history: PatientHeadingRevision[];
}

export interface AllergyItem {
  allergen: string;
  reaction: string;
  severity: string;
  provenance?: {
    source_record_id: string;
    recorded_by: string;
    recorded_on: string;
  };
}

export interface AdverseReactionItem {
  medicine_name: string;
  symptom: string;
  occurred_on: string | null;
  provenance?: {
    source_record_id: string;
    recorded_by: string;
    recorded_on: string;
  };
}

export interface MedicalConditionItem {
  condition_name: string;
  condition_status: string;
  is_contraindication_target: boolean;
  provenance?: {
    source_record_id: string;
    recorded_by: string;
    recorded_on: string;
  };
}

export interface ConcurrentMedicationItem {
  medicine_name: string;
  category: string;
  started_on: string;
  ended_on: string | null;
  prescriber_institution: string | null;
  provenance?: {
    source_record_id: string;
    recorded_by: string;
    recorded_on: string;
  };
}

export interface PatientMedicalProfile {
  id: string;
  corporate_id: string;
  patient_id: string;
  allergies: AllergyItem[];
  adverse_reactions: AdverseReactionItem[];
  medical_conditions: MedicalConditionItem[];
  concurrent_medications: ConcurrentMedicationItem[];
  active_concurrent_medications: ConcurrentMedicationItem[];
  lifestyle?: unknown;
  generic_preference?: unknown;
  family_pharmacist?: unknown;
}

export interface RegisterPatientInput {
  last_name: string;
  first_name: string;
  last_name_kana: string;
  first_name_kana: string;
  birth_date?: string | null;
}

export interface ChangePatientHeadingInput {
  expected_revision: number;
  summary?: string | null;
  notes?: string | null;
}
