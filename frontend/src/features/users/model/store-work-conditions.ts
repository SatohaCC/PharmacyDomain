export interface StoreWorkCondition {
  effective_from: string;
  weekly_hours: string | null;
  duty: string;
  recorded_at: string;
  recorded_by: string;
}
export interface StoreAffiliation {
  store_id: string;
  starts_on: string;
  ends_on: string | null;
  is_primary: boolean;
  is_managing_pharmacist: boolean;
  current: StoreWorkCondition | null;
  history: StoreWorkCondition[];
}
