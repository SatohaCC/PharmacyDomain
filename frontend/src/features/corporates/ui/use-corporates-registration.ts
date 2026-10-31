import { useSubmission } from "../../../shared/forms/use-submission";
import { registerContract } from "../api/corporate-api";
import { text } from "../../../shared/forms/values";
export function useCorporateRegistration({
  onComplete,
}: {
  onComplete: (id: string) => Promise<void>;
}) {
  const submit = async (d: FormData) => {
    const created = await registerContract({
      administrator: {
        last_name: text(d, "admin_last"),
        first_name: text(d, "admin_first"),
        last_name_kana: text(d, "admin_last_kana"),
        first_name_kana: text(d, "admin_first_kana"),
      },
      email: text(d, "email"),
      initial_password: String(d.get("initial_password") || ""),
      name: text(d, "name"),
      representative_last_name: text(d, "last"),
      representative_first_name: text(d, "first"),
    });
    await onComplete(created.id);
  };
  return { submit: useSubmission(submit) };
}
