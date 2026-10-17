import { Paragraph } from "../shared/ui/layout/elements";
import { ApiError, errorText } from "../shared/api/errors";
import { Alert } from "../shared/ui/feedback/alert";
export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <Alert>
      {errorText(error)}
      {error instanceof ApiError && error.status === 401 && (
        <Paragraph>
          <a href="/login">ログイン画面へ</a>
        </Paragraph>
      )}
    </Alert>
  ) : null;
}
