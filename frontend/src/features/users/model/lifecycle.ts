export interface UserLifecycleState {
  staffId: string;
  staffName: string;
  personId: string;
  accountId: string;
  membershipId: string;
  isStaffActive: boolean;
  accountStatus: "active" | "suspended";
  membershipStatus: "active" | "suspended";
  storeName?: string;
  retiredOn?: string;
}
