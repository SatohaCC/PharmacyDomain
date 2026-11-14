import { createFileRoute } from "@tanstack/react-router";
import { listPatients } from "../../../features/patients/api/patient-api";
import { listPatientCareEvents } from "../../../features/prescriptions/api/prescription-api";
import { Panel, Stack } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  Heading,
  SectionHeading,
  Paragraph,
  ActionRow,
  Cards,
  Card,
  MetaText,
  StatValue,
  Title,
} from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { EmptyState } from "../../../shared/ui/feedback/alert";

export const Route = createFileRoute("/stores/$storeId/home")({
  loader: async ({ params, context, abortController }) => {
    const corporateId = context.actor.corporate_id;
    if (!corporateId) {
      throw new Error("所属法人が設定されていません。");
    }
    const [events, patients] = await Promise.all([
      listPatientCareEvents(
        corporateId,
        params.storeId,
        undefined,
        abortController.signal,
      ).catch(() => []),
      listPatients(corporateId, undefined, abortController.signal).catch(
        () => [],
      ),
    ]);

    const patientNamesById: Record<string, string> = {};
    for (const p of patients) {
      patientNamesById[p.id] = `${p.last_name} ${p.first_name}`;
    }

    const sortedEvents = [...events]
      .sort((a, b) => (b.occurred_at ?? "").localeCompare(a.occurred_at ?? ""))
      .slice(0, 20);

    return {
      storeName: context.currentStore?.name ?? "調剤現場業務",
      events: sortedEvents,
      patientCount: patients.length,
      patientNamesById,
    };
  },
  component: StoreHomePage,
});

function StoreHomePage() {
  const { storeId } = Route.useParams();
  const { storeName, events, patientCount, patientNamesById } =
    Route.useLoaderData();

  return (
    <Stack gap="normal">
      <Panel>
        <Title>
          <div>
            <Heading>業務ホーム — {storeName}</Heading>
            <Paragraph>
              店舗の患者状況と直近の受付・対応イベントを確認し、各業務画面へ移動できます。
            </Paragraph>
          </div>
          <ActionRow>
            <Link
              href={`/stores/${encodeURIComponent(storeId)}/patients`}
              appearance="action"
            >
              患者一覧・検索へ
            </Link>
            <Link
              href={`/stores/${encodeURIComponent(storeId)}/settings`}
              appearance="action"
            >
              店舗設定
            </Link>
            <Link
              href={`/stores/${encodeURIComponent(storeId)}/my-settings`}
              appearance="action"
            >
              マイ設定
            </Link>
          </ActionRow>
        </Title>
      </Panel>

      <Cards>
        <Card>
          <MetaText>登録患者数</MetaText>
          <StatValue>{patientCount} 名</StatValue>
          <ActionRow>
            <Link href={`/stores/${encodeURIComponent(storeId)}/patients`}>
              患者一覧・検索を開く
            </Link>
          </ActionRow>
        </Card>
        <Card>
          <MetaText>直近の受付・対応イベント</MetaText>
          <StatValue>{events.length} 件</StatValue>
          <MetaText>最新20件まで表示</MetaText>
        </Card>
      </Cards>

      <Panel>
        <SectionHeading>直近の受付・対応イベント</SectionHeading>
        {events.length === 0 ? (
          <EmptyState>この店舗の受付・対応イベントはまだありません。</EmptyState>
        ) : (
          <Cards>
            {events.map((ev) => {
              const patientName =
                patientNamesById[ev.patient_id] ?? ev.patient_id;
              return (
                <Card key={ev.event_id}>
                  <ActionRow>
                    <strong>{patientName}</strong>
                    <Badge>{ev.event_type_name ?? "対応イベント"}</Badge>
                  </ActionRow>
                  <MetaText>
                    {ev.occurred_at ? ev.occurred_at.slice(0, 10) : "日時未設定"}
                  </MetaText>
                  <ActionRow>
                    <Link
                      href={`/stores/${encodeURIComponent(storeId)}/patients/${encodeURIComponent(ev.patient_id)}`}
                    >
                      患者詳細・薬歴を開く
                    </Link>
                  </ActionRow>
                </Card>
              );
            })}
          </Cards>
        )}
      </Panel>
    </Stack>
  );
}
