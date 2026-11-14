import { createFileRoute } from "@tanstack/react-router";
import { listPatients } from "../../../features/patients/api/patient-api";
import { listPatientCareEvents } from "../../../features/prescriptions/api/prescription-api";
import { Panel, Stack } from "../../../shared/ui/Panel";
import { Badge } from "../../../shared/ui/Badge";
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
} from "../../../shared/ui/Elements";
import { Link } from "../../../shared/ui/Link";
import { EmptyState } from "../../../shared/ui/Alert";
import {
  Table,
  TableHeader,
  TableRowHeader,
  TableCell,
} from "../../../shared/ui/Table";

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
        <SectionHeading id="recent-receptions-heading">
          直近の受付・対応イベント
        </SectionHeading>
        {events.length === 0 ? (
          <EmptyState>
            この店舗の受付・対応イベントはまだありません。
          </EmptyState>
        ) : (
          <Table ariaLabelledBy="recent-receptions-heading">
            <thead>
              <tr>
                <TableHeader>受付・発生日</TableHeader>
                <TableHeader>患者名</TableHeader>
                <TableHeader>種別</TableHeader>
                <TableHeader>操作</TableHeader>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => {
                const patientName =
                  patientNamesById[ev.patient_id] ?? ev.patient_id;
                const occurredDate = ev.occurred_at
                  ? ev.occurred_at.slice(0, 10)
                  : "日時未設定";
                const eventType = ev.event_type_name ?? "対応イベント";
                const query = new URLSearchParams({ eventId: ev.event_id });
                if (ev.medication_history_id) {
                  query.set("historyId", ev.medication_history_id);
                }
                return (
                  <tr key={ev.event_id}>
                    <TableCell>{occurredDate}</TableCell>
                    <TableRowHeader>{patientName}</TableRowHeader>
                    <TableCell>
                      <Badge>{eventType}</Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/stores/${encodeURIComponent(storeId)}/patients/${encodeURIComponent(ev.patient_id)}?${query.toString()}`}
                        ariaLabel={`患者詳細・薬歴を開く（${patientName}・${occurredDate}・${eventType}）`}
                      >
                        患者詳細・薬歴を開く
                      </Link>
                    </TableCell>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Panel>
    </Stack>
  );
}
