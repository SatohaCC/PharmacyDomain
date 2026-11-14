import { useEffect, useMemo, useState } from "react";
import { createFileRoute, useRouter, useRouterState } from "@tanstack/react-router";
import {
  getPatient,
  getPatientHeading,
  getMedicalProfile,
  changePatientHeading,
  listPatients,
} from "../../../../../features/patients/api/patient-api";
import { PatientDetailView } from "../../../../../features/patients/components/PatientDetailView";
import type { PatientDetail } from "../../../../../features/patients/model/patient";
import {
  getCategoryCatalog,
  listPatientMedicationHistories,
  listStoreCurrentRecordFields,
  type MedicationHistoryDto,
} from "../../../../../features/medication_history/api/record-api";
import {
  listMedicationHistoryBlocks,
  saveMedicationHistoryBlocks,
} from "../../../../../features/medication_history/api/block-api";
import { finalizeMedicationHistory } from "../../../../../features/medication_history/api/finalization-api";
import {
  DEFAULT_SOAP_CATEGORIES,
  type CategoryOption,
  type CurrentRecordHearingItem,
  type MedicationHistoryBlock,
  type MedicationHistoryBlockInput,
} from "../../../../../features/medication_history/model/block";
import {
  DETAIL_FOOTER_ITEMS,
  filterByStoreId,
  loadStoreFooterOrder,
  orderFooterItems,
  type DetailFooterMode,
  type PrescriptionSummaryForHistory,
} from "../../../../../features/medication_history/model/history-modes";
import {
  BlocksEditorView,
  type BlockItemState,
} from "../../../../../features/medication_history/components/BlocksEditorView";
import {
  CenterWorkspacePanel,
  type InteractionAuditSummary,
} from "../../../../../features/medication_history/components/CenterWorkspacePanel";
import {
  auditPrescriptionInteractions,
  getPrescription,
  listPatientCareEvents,
  type CareEventDto,
} from "../../../../../features/prescriptions/api/prescription-api";
import { ThreePane } from "../../../../../shared/component/ThreePane";
import { DetailFooterBar } from "../../../../../shared/component/DetailFooterBar";
import { Panel } from "../../../../../shared/ui/Panel";
import { Subheading, Paragraph } from "../../../../../shared/ui/Elements";
import { EmptyState } from "../../../../../shared/ui/Alert";
import { ApiError, errorText } from "../../../../../shared/api/errors";

export const Route = createFileRoute(
  "/stores/$storeId/patients/$patientId/",
)({
  loader: async ({ params, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    const today = new Date().toISOString().slice(0, 10);
    const [
      patient,
      headingResult,
      medicalProfileResult,
      historiesResult,
      catalogResult,
      fieldsResult,
      careEventsResult,
    ] = await Promise.all([
      getPatient(corporateId, params.patientId, abortController.signal).catch(
        async (err: unknown): Promise<PatientDetail> => {
          if (err instanceof ApiError && err.status === 403) {
            const list = await listPatients(
              corporateId,
              undefined,
              abortController.signal,
            );
            const found = list.find((p) => p.id === params.patientId);
            if (found) {
              return {
                id: found.id,
                patient_number: found.patient_number,
                corporate_id: found.corporate_id,
                last_name: found.last_name,
                first_name: found.first_name,
                last_name_kana: found.last_name_kana,
                first_name_kana: found.first_name_kana,
                birth_date: found.birth_date,
                gender: found.gender ?? null,
                postal_code: null,
                address: null,
                phone_number: found.phone_number ?? null,
                status: found.status,
                merged_into_id: null,
                status_history: [],
                profile_history: [],
              };
            }
          }
          throw err;
        },
      ),
      getPatientHeading(corporateId, params.patientId, abortController.signal)
        .then((data) => ({ data, error: null }))
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 404) {
            return { data: null, error: null };
          }
          return { data: null, error: errorText(err) };
        }),
      getMedicalProfile(
        corporateId,
        params.patientId,
        today,
        abortController.signal,
      )
        .then((data) => ({ data, error: null }))
        .catch((err: unknown) => {
          if (err instanceof ApiError && err.status === 404) {
            return { data: null, error: null };
          }
          return { data: null, error: errorText(err) };
        }),
      listPatientMedicationHistories(
        corporateId,
        params.patientId,
        abortController.signal,
      ).catch(() => [] as MedicationHistoryDto[]),
      getCategoryCatalog(corporateId, abortController.signal).catch(() => null),
      listStoreCurrentRecordFields(
        corporateId,
        params.storeId,
        abortController.signal,
      ).catch(() => []),
      listPatientCareEvents(
        corporateId,
        params.storeId,
        params.patientId,
        abortController.signal,
      ).catch(() => [] as CareEventDto[]),
    ]);

    const sortedHistories = filterByStoreId(historiesResult, params.storeId).sort(
      (a, b) => {
        const da = a.counseled_at ?? a.event_occurred_at ?? "";
        const db = b.counseled_at ?? b.event_occurred_at ?? "";
        return db.localeCompare(da);
      },
    );

    const sortedEvents = [...careEventsResult].sort((a, b) =>
      (b.occurred_at ?? "").localeCompare(a.occurred_at ?? ""),
    );

    const prescriptionIds = Array.from(
      new Set(
        [
          ...sortedHistories.map((h) => h.prescription_id),
          ...sortedEvents.map((ev) => ev.prescription_id),
        ].filter((id): id is string => Boolean(id)),
      ),
    );

    const loadedPrescriptions = await Promise.all(
      prescriptionIds.map((rxId) =>
        getPrescription(corporateId, rxId, abortController.signal).catch(
          () => null,
        ),
      ),
    );

    const prescriptionsById: Record<string, PrescriptionSummaryForHistory> = {};
    for (const rx of loadedPrescriptions) {
      if (!rx || rx.store_id !== params.storeId) continue;
      prescriptionsById[rx.id] = {
        id: rx.id,
        document_number: rx.document_number,
        issued_date: rx.period.issued_date,
        institution_name: rx.medical_institution.name ?? "医療機関未設定",
        rps: rx.rps.map((rp) => ({
          rp_number: rp.rp_number,
          category: rp.category,
          quantity: rp.quantity,
          dosage_name: rp.dosage_instruction.name ?? "",
          medicines: rp.medicines.map((m) => ({
            code: m.code ?? null,
            name: m.name,
            amount: m.amount,
            unit: m.unit,
          })),
        })),
      };
    }

    const availableCategories: CategoryOption[] =
      catalogResult && catalogResult.major_categories.length > 0
        ? catalogResult.major_categories
            .filter((c) => c.is_enabled)
            .sort((a, b) => a.display_order - b.display_order)
            .map((c) => ({
              code: c.code,
              name: c.name,
              badge_label: c.code.toUpperCase(),
            }))
        : DEFAULT_SOAP_CATEGORIES;

    const hearingItems: CurrentRecordHearingItem[] = fieldsResult.map((f) => ({
      field_id: f.id,
      label: f.label,
      value: "",
      category_code: f.category_code ?? undefined,
    }));

    return {
      patient,
      heading: headingResult.data,
      headingFetchError: headingResult.error,
      medicalProfile: medicalProfileResult.data,
      medicalProfileFetchError: medicalProfileResult.error,
      histories: sortedHistories,
      careEvents: sortedEvents,
      prescriptionsById,
      availableCategories,
      hearingItems,
      corporateId,
    };
  },
  component: PatientDetailComponent,
});

function buildInitialBlocks(
  record: MedicationHistoryDto,
  loadedBlocks: MedicationHistoryBlock[],
): BlockItemState[] {
  if (loadedBlocks.length > 0) {
    return loadedBlocks.map((b) => ({
      ...b,
      clientKey: b.id,
    }));
  }
  const soap = record.effective_soap ?? record.soap;
  const join = (list: Array<{ text: string }> | undefined) =>
    (list ?? [])
      .map((item) => item.text.trim())
      .filter(Boolean)
      .join("\n");
  const entries: Array<[string, string]> = [
    ["s", join(soap.subjective)],
    ["o", join(soap.objective)],
    ["a", join(soap.assessment)],
    ["p", join(soap.plan)],
  ];
  return entries
    .filter(([, text]) => text.length > 0)
    .map(([code, text], idx) => ({
      clientKey: `${record.id}-${code}-${idx}`,
      category_code: code,
      category_badge_label: code.toUpperCase(),
      content: text,
      display_order: (idx + 1) * 10,
      source_module: "soap",
    }));
}

function PatientDetailComponent() {
  const { storeId, patientId } = Route.useParams();
  const {
    patient,
    heading,
    headingFetchError,
    medicalProfile,
    medicalProfileFetchError,
    histories,
    careEvents,
    prescriptionsById,
    availableCategories,
    hearingItems,
    corporateId,
  } = Route.useLoaderData();
  const router = useRouter();
  const searchStr = useRouterState({ select: (s) => s.location.searchStr });

  const initialRecordId = useMemo(() => {
    const params = new URLSearchParams(searchStr);
    const historyId = params.get("historyId");
    if (historyId && histories.some((h) => h.id === historyId)) {
      return historyId;
    }
    const eventId = params.get("eventId");
    if (eventId) {
      const ev = careEvents.find((item) => item.event_id === eventId);
      const matched =
        (ev?.medication_history_id
          ? histories.find((h) => h.id === ev.medication_history_id)
          : undefined) ??
        histories.find((h) => h.event_id === eventId) ??
        (ev?.prescription_id
          ? histories.find((h) => h.prescription_id === ev.prescription_id)
          : undefined);
      if (matched) {
        return matched.id;
      }
    }
    return histories[0]?.id ?? null;
  }, [searchStr, histories, careEvents]);

  const [activeMode, setActiveMode] =
    useState<DetailFooterMode>("past_history");
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(
    () => initialRecordId,
  );
  const [loadedBlocks, setLoadedBlocks] = useState<MedicationHistoryBlock[]>(
    [],
  );
  const [blocksLoadedForId, setBlocksLoadedForId] = useState<string | null>(
    null,
  );
  const [auditReport, setAuditReport] =
    useState<InteractionAuditSummary | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const selectedRecord = useMemo(
    () =>
      histories.find((h) => h.id === selectedRecordId) ?? histories[0] ?? null,
    [histories, selectedRecordId],
  );

  useEffect(() => {
    if (!selectedRecord) {
      return;
    }
    const controller = new AbortController();
    listMedicationHistoryBlocks(
      corporateId,
      selectedRecord.id,
      storeId,
      controller.signal,
    )
      .then((blocks) => {
        setLoadedBlocks(blocks);
        setBlocksLoadedForId(selectedRecord.id);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setLoadedBlocks([]);
          setBlocksLoadedForId(selectedRecord.id);
        }
      });
    return () => controller.abort();
  }, [corporateId, selectedRecord, storeId]);

  const handleUpdateHeading = async (input: {
    expectedRevision: number;
    summary: string | null;
    notes: string | null;
  }) => {
    await changePatientHeading(corporateId, patientId, {
      expected_revision: input.expectedRevision,
      summary: input.summary,
      notes: input.notes,
    });
    await router.invalidate();
  };

  const handleSaveBlocks = async (blocks: MedicationHistoryBlockInput[]) => {
    if (!selectedRecord) return;
    const saved = await saveMedicationHistoryBlocks(
      corporateId,
      selectedRecord.id,
      storeId,
      blocks,
    );
    setLoadedBlocks(saved);
    await router.invalidate();
  };

  const handleRunAudit = async (prescriptionId: string) => {
    setAuditLoading(true);
    setAuditError(null);
    try {
      const rx = prescriptionsById[prescriptionId];
      const yjCodes = rx
        ? rx.rps
            .flatMap((rp) => rp.medicines.map((m) => m.code))
            .filter((code): code is string => Boolean(code))
        : [];
      const report = await auditPrescriptionInteractions(corporateId, yjCodes);
      setAuditReport({
        prescriptionId,
        documentNumber: rx?.document_number ?? prescriptionId,
        totalCombinations: report.total_combinations,
        contraindicatedCount: report.contraindicated_count,
        precautionCount: report.precaution_count,
        pairs: report.pairs.map((p) => ({
          first_name: p.medicine_a,
          second_name: p.medicine_b,
          severity: p.severity,
          description: `${p.clinical_condition} / ${p.recommendation}`,
        })),
      });
    } catch (err: unknown) {
      setAuditError(errorText(err));
    } finally {
      setAuditLoading(false);
    }
  };

  const editorKey = selectedRecord
    ? `${selectedRecord.id}-${blocksLoadedForId === selectedRecord.id ? "loaded" : "init"}`
    : "none";

  const initialBlocks = useMemo(
    () =>
      selectedRecord ? buildInitialBlocks(selectedRecord, loadedBlocks) : [],
    [selectedRecord, loadedBlocks],
  );

  return (
    <ThreePane
      left={
        <PatientDetailView
          patient={patient}
          heading={heading}
          headingFetchError={headingFetchError}
          medicalProfile={medicalProfile}
          medicalProfileFetchError={medicalProfileFetchError}
          storeId={storeId}
          onUpdateHeading={handleUpdateHeading}
        />
      }
      center={
        <CenterWorkspacePanel
          activeMode={activeMode}
          records={histories}
          prescriptionsById={prescriptionsById}
          careEvents={careEvents}
          selectedRecordId={selectedRecord?.id ?? null}
          onSelectRecord={(id) => setSelectedRecordId(id)}
          newEntryHref={`/stores/${encodeURIComponent(storeId)}/patients/${encodeURIComponent(patientId)}/entries/new`}
          patientSummary={{
            patientName: `${patient.last_name} ${patient.first_name}`,
            birthDate: patient.birth_date,
            allergiesCount: medicalProfile?.allergies?.length ?? 0,
            sideEffectsCount: medicalProfile?.adverse_reactions?.length ?? 0,
            medicalHistoriesCount:
              medicalProfile?.medical_conditions?.length ?? 0,
            concomitantMedsCount:
              medicalProfile?.concurrent_medications?.length ?? 0,
          }}
          auditReport={auditReport}
          auditLoading={auditLoading}
          auditError={auditError}
          onRunAudit={(rxId) => void handleRunAudit(rxId)}
        />
      }
      right={
        selectedRecord ? (
          <BlocksEditorView
            key={editorKey}
            initialBlocks={initialBlocks}
            hearingItems={hearingItems}
            availableCategories={availableCategories}
            isDraft={selectedRecord.status === "draft"}
            readOnly={selectedRecord.status !== "draft"}
            onSave={handleSaveBlocks}
            finalizationReview={{
              pendingExternalCorrections: selectedRecord.external_corrections
                .filter((c) => c.status !== "acknowledged")
                .map((c) => ({
                  correction_id: c.correction_id,
                  reason: c.reason,
                  status: c.status,
                })),
              onFinalize: async (input) => {
                await finalizeMedicationHistory(
                  corporateId,
                  selectedRecord.id,
                  input,
                );
                await router.invalidate();
              },
            }}
          />
        ) : (
          <Panel>
            <Subheading>今回の薬歴・記載</Subheading>
            <Paragraph>薬歴が選択されていません</Paragraph>
            <EmptyState>
              まだ薬歴が登録されていないため編集欄を表示できません。
            </EmptyState>
          </Panel>
        )
      }
      footer={
        <DetailFooterBar
          ariaLabel="患者詳細業務メニュー"
          items={orderFooterItems(
            DETAIL_FOOTER_ITEMS,
            loadStoreFooterOrder(storeId),
          )}
          activeId={activeMode}
          onSelect={(id) => setActiveMode(id as DetailFooterMode)}
        />
      }
    />
  );
}
