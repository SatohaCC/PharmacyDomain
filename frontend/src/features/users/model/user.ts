export interface UserList {
  items: {
    id: string;
    person_id: string;
    role: string;
    status: string;
    account_status: string | null;
    staff_id?: string | null;
  }[];
  next_cursor?: string | null;
}
