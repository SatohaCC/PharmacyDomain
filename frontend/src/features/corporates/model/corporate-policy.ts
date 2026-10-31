export interface PolicySetting {
  value: boolean;
  overridable: boolean;
}

export interface CorporatePolicy {
  require_prescription_audit: PolicySetting;
  prohibit_self_verification: PolicySetting;
}
