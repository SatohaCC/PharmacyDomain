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

export interface StaffDetail {
  id: string;
  corporate_id: string;
  last_name: string;
  first_name: string;
  last_name_kana: string;
  first_name_kana: string;
  job_title: string | null;
  code: string | null;
  phone_number: string | null;
  email: string | null;
  employment_type: string;
  weekly_contract_hours: number | null;
  effective_weekly_hours: number | null;
  effective_full_time_equivalent: number | null;
  is_active: boolean;
  is_pharmacist: boolean;
  status?: string;
  leave_reason?: string | null;
}

export interface UserDetail {
  id: string;
  account_id: string;
  person_id: string;
  corporate_id: string;
  role: string;
  status: string;
  account_status: string;
  store_ids: string[];
  staff_id: string | null;
  staff?: StaffDetail | null;
}
