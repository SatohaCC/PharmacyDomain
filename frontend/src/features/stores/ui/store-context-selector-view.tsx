import { SelectField } from "../../../shared/ui/controls/select-field";
import type { SelectableStore } from "../model/selectable-store";

export interface StoreContextSelectorViewProps {
  stores: readonly SelectableStore[];
  selectedStoreId: string | null;
  onSelectStore: (storeId: string) => void;
  disabled?: boolean;
}

export function StoreContextSelectorView({
  stores,
  selectedStoreId,
  onSelectStore,
  disabled = false,
}: StoreContextSelectorViewProps) {
  if (stores.length === 0) {
    return null;
  }

  const options = stores.map((s) => ({
    value: s.id,
    label: s.code ? `${s.name} (${s.code})` : s.name,
  }));

  return (
    <div data-testid="store-context-selector">
      <SelectField
        label="勤務店舗"
        value={selectedStoreId || ""}
        options={options}
        onValueChange={onSelectStore}
        disabled={disabled}
      />
    </div>
  );
}
