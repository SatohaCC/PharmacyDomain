import { useSubmission } from "../../../shared/forms/use-submission";
import { createStore } from "../api/store-api";
import { text, optional } from "../../../shared/forms/values";
export function useStoreRegistration({
  corporateId,
  onComplete,
}: {
  corporateId: string;
  onComplete: () => Promise<void>;
}) {
  const submit = async (d: FormData) => {
    const created = await createStore(corporateId, {
      name: text(d, "name"),
      name_kana: text(d, "name_kana"),
      postal_code: text(d, "postal_code"),
      address: text(d, "address"),
      phone_number: text(d, "phone_number"),
      name_romaji: optional(d, "name_romaji"),
      fax_number: optional(d, "fax_number"),
      email: optional(d, "email"),
      code: optional(d, "code"),
      insurance_pharmacy_number: optional(d, "insurance_pharmacy_number"),
    });
    void created;
    await onComplete();
  };
  return { submit: useSubmission(submit) };
}
