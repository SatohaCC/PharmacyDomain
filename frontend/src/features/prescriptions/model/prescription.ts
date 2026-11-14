export interface RegisterPrescriptionBody {
  store_id: string;
  patient_id: string;
  source_type: "paper_qr" | "electronic";
  document_number: string;
  issued_date: string;
  medical_institution: {
    code_type: string;
    code: string;
    prefecture_code: string;
    name: string;
  };
  department: {
    code_type: string;
    name: string;
  };
  prescriber: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  };
  rps: Array<{
    rp_number: number;
    category: string;
    quantity: number;
    dosage_instruction: {
      code_type: string;
      name: string;
    };
    medicines: Array<{
      line_number: number;
      code_type: string;
      code: string;
      name: string;
      amount: string;
      unit: string;
      unequal_doses: string[];
      supplements: never[];
    }>;
    dosage_supplements: never[];
  }>;
}

export interface MedicinePreset {
  code: string;
  name: string;
  unit: string;
}

export const SAMPLE_MEDICINE_PRESETS: MedicinePreset[] = [
  { code: "2171022F1020", name: "アムロジピン錠5mg", unit: "錠" },
  { code: "1149019F1020", name: "ロキソプロフェンNa錠60mg", unit: "錠" },
  { code: "2329021F1020", name: "レバミピド錠100mg", unit: "錠" },
  { code: "6131001M1020", name: "アモキシシリンカプセル250mg", unit: "カプセル" },
  { code: "1141007F1020", name: "カロナール錠200", unit: "錠" },
];

export interface PrescriptionRpRowInput {
  category: "internal" | "prn" | "topical";
  quantity: number;
  dosageName: string;
  medicineCode: string;
  medicineName: string;
  amount: string;
  unit: string;
}

export interface PrescriptionEntryFormInput {
  storeId: string;
  patientId: string;
  sourceType: "paper_qr" | "electronic";
  documentNumber: string;
  issuedDate: string;
  institutionName: string;
  institutionCode: string;
  prefectureCode: string;
  departmentName: string;
  prescriberLastName: string;
  prescriberFirstName: string;
  prescriberLastNameKana: string;
  prescriberFirstNameKana: string;
  rps: PrescriptionRpRowInput[];
}

/** フォーム入力から処方箋登録API用のリクエストボディを組み立てる。 */
export function buildRegisterPrescriptionBody(
  input: PrescriptionEntryFormInput,
): RegisterPrescriptionBody {
  return {
    store_id: input.storeId,
    patient_id: input.patientId,
    source_type: input.sourceType,
    document_number: input.documentNumber.trim(),
    issued_date: input.issuedDate,
    medical_institution: {
      code_type: "medical",
      code: input.institutionCode.trim(),
      prefecture_code: input.prefectureCode.trim(),
      name: input.institutionName.trim(),
    },
    department: {
      code_type: "none",
      name: input.departmentName.trim(),
    },
    prescriber: {
      last_name: input.prescriberLastName.trim(),
      first_name: input.prescriberFirstName.trim(),
      last_name_kana: input.prescriberLastNameKana.trim(),
      first_name_kana: input.prescriberFirstNameKana.trim(),
    },
    rps: input.rps.map((rp, idx) => ({
      rp_number: idx + 1,
      category: rp.category,
      quantity: rp.quantity,
      dosage_instruction: {
        code_type: "none",
        name: rp.dosageName.trim(),
      },
      medicines: [
        {
          line_number: 1,
          code_type: "yj",
          code: rp.medicineCode.trim(),
          name: rp.medicineName.trim(),
          amount: rp.amount.trim(),
          unit: rp.unit.trim(),
          unequal_doses: [],
          supplements: [],
        },
      ],
      dosage_supplements: [],
    })),
  };
}
