import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  Cards,
} from "../../../shared/ui/layout/elements";
import { ActionCard } from "../../../shared/ui/navigation/action-card";

export function CorporateOverviewView({
  corporateId,
}: {
  corporateId: string;
}) {
  return (
    <Panel>
      <Subheading>法人の管理</Subheading>
      <Paragraph>店舗や法人を利用するユーザーを登録できます。</Paragraph>
      <Cards>
        <ActionCard
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/stores/new`}
          title="店舗を登録"
          description="店舗名・所在地・連絡先"
        />
        <ActionCard
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/users/new`}
          title="ユーザーを登録"
          description="本人登録・ログイン情報・権限"
        />
      </Cards>
    </Panel>
  );
}
