export const text = (data: FormData, key: string) =>
  String(data.get(key) || "").trim();
export const optional = (data: FormData, key: string) =>
  text(data, key) || null;
