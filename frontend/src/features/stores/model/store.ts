export interface Store {
  id: string;
  name: string;
  name_kana: string;
  code: string | null;
}
export interface StoreInput {
  name: string;
  name_kana: string;
  postal_code: string;
  address: string;
  phone_number: string;
  name_romaji: string | null;
  fax_number: string | null;
  email: string | null;
  code: string | null;
  insurance_pharmacy_number: string | null;
}
