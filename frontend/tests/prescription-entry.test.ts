import { describe, expect, it } from "vitest";
import { buildRegisterPrescriptionBody } from "../src/features/prescriptions/model/prescription";

describe("buildRegisterPrescriptionBody", () => {
  it("フォーム入力から処方箋登録APIの正しいリクエストボディを組み立てる", () => {
    const body = buildRegisterPrescriptionBody({
      storeId: "store-1",
      patientId: "patient-1",
      sourceType: "paper_qr",
      documentNumber: " RX-20261114-001 ",
      issuedDate: "2026-11-14",
      institutionName: " シード内科クリニック ",
      institutionCode: "1234567",
      prefectureCode: "13",
      departmentName: "内科",
      prescriberLastName: "鈴木",
      prescriberFirstName: "一郎",
      prescriberLastNameKana: "スズキ",
      prescriberFirstNameKana: "イチロウ",
      rps: [
        {
          category: "internal",
          quantity: 14,
          dosageName: "1日1回朝食後",
          medicineCode: "2171022F1020",
          medicineName: "アムロジピン錠5mg",
          amount: "1",
          unit: "錠",
        },
      ],
    });

    expect(body).toEqual({
      store_id: "store-1",
      patient_id: "patient-1",
      source_type: "paper_qr",
      document_number: "RX-20261114-001",
      issued_date: "2026-11-14",
      medical_institution: {
        code_type: "medical",
        code: "1234567",
        prefecture_code: "13",
        name: "シード内科クリニック",
      },
      department: {
        code_type: "none",
        name: "内科",
      },
      prescriber: {
        last_name: "鈴木",
        first_name: "一郎",
        last_name_kana: "スズキ",
        first_name_kana: "イチロウ",
      },
      rps: [
        {
          rp_number: 1,
          category: "internal",
          quantity: 14,
          dosage_instruction: {
            code_type: "none",
            name: "1日1回朝食後",
          },
          medicines: [
            {
              line_number: 1,
              code_type: "yj",
              code: "2171022F1020",
              name: "アムロジピン錠5mg",
              amount: "1",
              unit: "錠",
              unequal_doses: [],
              supplements: [],
            },
          ],
          dosage_supplements: [],
        },
      ],
    });
  });
});
