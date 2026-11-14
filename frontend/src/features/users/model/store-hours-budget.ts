import type { StoreAffiliation } from "./store-work-conditions";

export interface StoreHoursChange {
  store_id: string;
  starts_on: string;
  effective_from: string;
  weekly_hours: string | null;
}
const cents = (hours: string | null) => {
  if (hours == null || !/^\d+(?:\.\d{1,2})?$/.test(hours)) return null;
  const [whole, fraction = ""] = hours.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
};
export function assessStoreHoursBudget(
  contractHours: number | null | undefined,
  changes: StoreHoursChange[],
  existing: StoreAffiliation[],
  appliedOn: string,
) {
  const periods = existing.map((item) => ({
    store_id: item.store_id,
    starts_on: item.starts_on,
    ends_on: item.ends_on,
  }));
  const records = existing.flatMap((item) =>
    item.history.map((record) => ({
      store_id: item.store_id,
      effective_from: record.effective_from,
      weekly_hours: record.weekly_hours,
    })),
  );
  for (const change of changes) {
    if (
      !periods.some(
        (period) =>
          period.store_id === change.store_id &&
          period.starts_on <= change.effective_from &&
          (!period.ends_on || period.ends_on >= change.effective_from),
      )
    )
      periods.push({
        store_id: change.store_id,
        starts_on: change.starts_on,
        ends_on: null,
      });
    records.push(change);
  }
  const dates = [
    ...new Set([
      appliedOn,
      ...records.map((item) => item.effective_from),
      ...periods.map((item) => item.starts_on),
    ]),
  ]
    .filter((day) => day >= appliedOn)
    .sort();
  let maximum = 0;
  let exceededOn: string | null = null;
  let incomplete = false;
  for (const day of dates) {
    let total = 0;
    for (const store of new Set(periods.map((item) => item.store_id))) {
      const period = periods.find(
        (item) =>
          item.store_id === store &&
          item.starts_on <= day &&
          (!item.ends_on || day <= item.ends_on),
      );
      if (!period) continue;
      const current = records
        .filter(
          (item) =>
            item.store_id === store &&
            period.starts_on <= item.effective_from &&
            item.effective_from <= day,
        )
        .sort((a, b) => a.effective_from.localeCompare(b.effective_from))
        .at(-1);
      const value = cents(current?.weekly_hours ?? null);
      if (value == null) incomplete = true;
      else total += value;
    }
    maximum = Math.max(maximum, total);
    if (
      contractHours != null &&
      total > Math.round(contractHours * 100) &&
      exceededOn == null
    )
      exceededOn = day;
  }
  return { maximumHours: maximum / 100, exceededOn, incomplete };
}
