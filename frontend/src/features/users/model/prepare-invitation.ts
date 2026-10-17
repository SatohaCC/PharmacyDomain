export interface RegistrationProgress {
  personId?: string;
  staffId?: string;
  linked?: boolean;
  uncertain?: boolean;
}
interface Operations {
  createPerson: () => Promise<string>;
  prepareStaff?: (personId: string) => Promise<void>;
  isUncertain?: (error: unknown) => boolean;
  invite: (personId: string) => Promise<{ id: string; secret: string }>;
}
export async function prepareInvitation(
  progress: RegistrationProgress,
  ops: Operations,
  changed: () => void,
) {
  if (progress.uncertain)
    throw new Error(
      "前回の結果を確認してください。重複登録を避けるため再送を停止しました。",
    );
  try {
    if (!progress.personId) {
      progress.personId = await ops.createPerson();
      changed();
    }
    if (ops.prepareStaff) await ops.prepareStaff(progress.personId);
    return await ops.invite(progress.personId);
  } catch (error) {
    if (error instanceof TypeError || ops.isUncertain?.(error))
      progress.uncertain = true;
    changed();
    throw error;
  }
}
