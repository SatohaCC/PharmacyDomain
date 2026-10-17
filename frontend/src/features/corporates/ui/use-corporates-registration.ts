import { useSubmission } from "../../../shared/forms/use-submission";
import { createCorporate } from "../api/corporate-api";
import { text } from "../../../shared/forms/values";
export function useCorporateRegistration({
  onComplete,
}: {
  onComplete: (id: string) => Promise<void>;
}) {
  const submit = async (d: FormData) => {
    const created = await createCorporate({
      name: text(d, "name"),
      representative_last_name: text(d, "last"),
      representative_first_name: text(d, "first"),
    });
    await onComplete(created.id);
  };
  return { submit: useSubmission(submit) };
}
