import { useState } from "react";
import { CorporateOverviewView } from "./corporates-overview-view";
import type { Corporate } from "../model/corporate";
import { updateCorporateDetails } from "../api/corporate-api";

export function CorporateOverviewPage({
  corporate: initialCorporate,
  onRefresh,
}: {
  corporate: Corporate;
  onRefresh?: () => Promise<void>;
}) {
  const [corporate, setCorporate] = useState<Corporate>(initialCorporate);

  const handleUpdateDetails = async (details: {
    corporate_type?: string;
    corporate_number?: string | null;
    invoice_number?: string | null;
    postal_code?: string | null;
    address_line?: string | null;
    phone_number?: string | null;
    email?: string | null;
  }) => {
    await updateCorporateDetails(corporate.id, details);
    setCorporate((prev) => ({
      ...prev,
      ...details,
      corporate_type: details.corporate_type || undefined,
    }));
    if (onRefresh) {
      await onRefresh();
    }
  };

  return (
    <CorporateOverviewView
      corporate={corporate}
      onUpdateDetails={handleUpdateDetails}
    />
  );
}
