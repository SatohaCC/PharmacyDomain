export interface StorePolicy {
  require_prescription_audit: boolean | null;
  prohibit_self_verification: boolean | null;
}

export interface EffectivePolicyItem {
  value: boolean;
  source: "corporate" | "store";
}

export interface EffectivePolicy {
  require_prescription_audit: EffectivePolicyItem;
  prohibit_self_verification: EffectivePolicyItem;
}
