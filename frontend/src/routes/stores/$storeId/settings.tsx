import { createFileRoute, useRouter } from "@tanstack/react-router";
import { getStore } from "../../../features/stores/api/store-api";
import {
  getCategoryCatalog,
  listStoreCurrentRecordFields,
  saveStoreCurrentRecordFields,
  updateCategoryCatalog,
} from "../../../features/medication_history/api/record-api";
import {
  loadStoreFooterOrder,
  saveStoreFooterOrder,
} from "../../../features/medication_history/model/history-modes";
import {
  StoreSettingsView,
  type CurrentRecordFieldSettingItem,
  type MajorCategorySettingItem,
} from "../../../features/medication_history/components/StoreSettingsView";

export const Route = createFileRoute("/stores/$storeId/settings")({
  loader: async ({ params, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    const [store, catalog, fields] = await Promise.all([
      getStore(corporateId, params.storeId, abortController.signal).catch(
        () => null,
      ),
      getCategoryCatalog(corporateId, abortController.signal).catch(() => null),
      listStoreCurrentRecordFields(
        corporateId,
        params.storeId,
        abortController.signal,
      ).catch(() => []),
    ]);

    return {
      corporateId,
      store,
      catalog,
      fields,
      initialFooterOrder: loadStoreFooterOrder(params.storeId),
      canEditCatalog: context.actor.roles.some(
        (r) => r === "corporate_admin" || r === "vendor_system_admin",
      ),
    };
  },
  component: StoreSettingsPage,
});

function StoreSettingsPage() {
  const { storeId } = Route.useParams();
  const {
    corporateId,
    store,
    catalog,
    fields,
    initialFooterOrder,
    canEditCatalog,
  } = Route.useLoaderData();
  const router = useRouter();

  const handleSaveCategories = async (items: MajorCategorySettingItem[]) => {
    await updateCategoryCatalog(corporateId, {
      major_categories: items.map((item, idx) => ({
        code: item.code,
        name: item.name,
        display_order: (idx + 1) * 10,
        is_enabled: item.is_enabled,
      })),
      medium_categories: catalog?.medium_categories ?? [],
      current_record_fields: catalog?.current_record_fields ?? [],
    });
    await router.invalidate();
  };

  const handleSaveCurrentRecordFields = async (
    items: CurrentRecordFieldSettingItem[],
  ) => {
    await saveStoreCurrentRecordFields(
      corporateId,
      storeId,
      items.map((item, idx) => ({
        id: item.id,
        label: item.label,
        category_code: item.category_code ?? "s",
        display_order: (idx + 1) * 10,
        is_archived: !item.is_enabled,
      })),
    );
    await router.invalidate();
  };

  return (
    <StoreSettingsView
      store={
        store
          ? {
              id: store.id,
              name: store.name,
              code: store.code ?? "—",
              status: store.status,
            }
          : null
      }
      categories={catalog?.major_categories ?? []}
      currentRecordFields={fields.map((f) => ({
        id: f.id,
        label: f.label,
        category_code: f.category_code ?? null,
        display_order: f.display_order,
        is_enabled: !f.is_archived,
      }))}
      initialFooterOrder={initialFooterOrder}
      canEditCatalog={canEditCatalog}
      onSaveCategories={handleSaveCategories}
      onSaveCurrentRecordFields={handleSaveCurrentRecordFields}
      onSaveFooterOrder={(orderIds) => saveStoreFooterOrder(storeId, orderIds)}
    />
  );
}
