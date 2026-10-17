export interface Submission {
  submit: (data: FormData) => void;
  pending: boolean;
  blocked: boolean;
  error?: string;
  onLogin?: () => void;
}
