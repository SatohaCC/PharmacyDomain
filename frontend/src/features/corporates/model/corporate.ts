export interface Corporate {
  id: string;
  name: string;
  representative_name: string;
  is_active: boolean;
}
export interface CorporateSearch {
  name?: string;
  status?: string;
  cursor?: string;
}
export interface CorporateList {
  items: Corporate[];
  next_cursor: string | null;
}
export interface CorporateInput {
  name: string;
  representative_last_name: string;
  representative_first_name: string;
}
