import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { StoreFrame } from "./store-frame";
import { ThreePane } from "./three-pane";
import { DetailFooterBar } from "./detail-footer-bar";
import { Panel, Stack } from "./panel";
import { Subheading, SectionHeading, TextArea } from "./elements";
import { Badge } from "../data-display/badge";
import {
  PropertyList,
  PropertyRow,
  CompactInfoCard,
} from "../data-display/property-list";
import {
  ContrastMatrixFrame,
  ContrastMatrixRow,
  ContrastHeaderCell,
  ContrastSectionBar,
  ContrastCell,
  ContrastDiffText,
  ContrastStatusTag,
  ContrastSummaryBanner,
  type ContrastStatusTone,
} from "../data-display/contrast-matrix";
import { TimelineList, TimelineItem } from "../data-display/timeline";
import {
  Table,
  TableHeader,
  TableCell,
} from "../data-display/table";
import { Button } from "../controls/button";
import { Link } from "../navigation/link";

const meta = {
  title: "共通UI/レイアウト/患者詳細3ペイン",
  component: ThreePane,
  parameters: {
    layout: "fullscreen",
    standalone: true,
  },
} satisfies Meta<typeof ThreePane>;

export default meta;
type Story = StoryObj<typeof meta>;

interface DemoCell {
  kind: "med" | "discontinued" | "empty";
  name?: string;
  tone?: ContrastStatusTone;
  tagLabel?: string;
  doseText?: string;
  prevDoseText?: string;
  qtyText?: string;
  prevQtyText?: string;
}

interface DemoRow {
  name: string;
  cells: [DemoCell, DemoCell, DemoCell];
}

interface DemoGroup {
  label: string;
  rows: DemoRow[];
}

const DEMO_GROUPS: DemoGroup[] = [
  {
    label: "RP1: 1日1回 朝食後",
    rows: [
      {
        name: "アムロジピン錠5mg",
        cells: [
          { kind: "med", name: "アムロジピン錠5mg", doseText: "1錠", qtyText: "14日分" },
          { kind: "med", name: "アムロジピン錠5mg", tone: "changed", tagLabel: "変更", prevDoseText: "1錠", doseText: "2錠", prevQtyText: "14日分", qtyText: "30日分" },
          { kind: "med", name: "アムロジピン錠5mg", tone: "unchanged", tagLabel: "継続", doseText: "2錠", qtyText: "30日分" },
        ],
      },
      {
        name: "オルメサルタン錠20mg",
        cells: [
          { kind: "med", name: "オルメサルタン錠20mg", doseText: "1錠", qtyText: "14日分" },
          { kind: "med", name: "オルメサルタン錠20mg", tone: "changed", tagLabel: "変更", doseText: "1錠", prevQtyText: "14日分", qtyText: "30日分" },
          { kind: "med", name: "オルメサルタン錠20mg", tone: "unchanged", tagLabel: "継続", doseText: "1錠", qtyText: "30日分" },
        ],
      },
      {
        name: "ジャヌビア錠50mg",
        cells: [
          { kind: "med", name: "ジャヌビア錠50mg", doseText: "1錠", qtyText: "30日分" },
          { kind: "med", name: "ジャヌビア錠50mg", tone: "unchanged", tagLabel: "継続", doseText: "1錠", qtyText: "30日分" },
          { kind: "discontinued", name: "ジャヌビア錠50mg", doseText: "1錠", qtyText: "30日分" },
        ],
      },
      {
        name: "フォシーガ錠10mg",
        cells: [
          { kind: "empty" },
          { kind: "empty" },
          { kind: "med", name: "フォシーガ錠10mg", tone: "added", tagLabel: "新規", doseText: "1錠", qtyText: "30日分" },
        ],
      },
      {
        name: "タケキャブ錠10mg",
        cells: [
          { kind: "med", name: "タケキャブ錠10mg", doseText: "1錠", qtyText: "14日分" },
          { kind: "med", name: "タケキャブ錠10mg", tone: "changed", tagLabel: "変更", doseText: "1錠", prevQtyText: "14日分", qtyText: "30日分" },
          { kind: "med", name: "タケキャブ錠10mg", tone: "unchanged", tagLabel: "継続", doseText: "1錠", qtyText: "30日分" },
        ],
      },
    ],
  },
  {
    label: "RP2: 1日2回 朝夕食後",
    rows: [
      {
        name: "メトホルミン塩酸塩錠250mg",
        cells: [
          { kind: "med", name: "メトホルミン塩酸塩錠250mg", doseText: "1錠", qtyText: "14日分" },
          { kind: "med", name: "メトホルミン塩酸塩錠250mg", tone: "changed", tagLabel: "変更", doseText: "1錠", prevQtyText: "14日分", qtyText: "30日分" },
          { kind: "med", name: "メトホルミン塩酸塩錠250mg", tone: "changed", tagLabel: "変更", prevDoseText: "1錠", doseText: "2錠", qtyText: "30日分" },
        ],
      },
    ],
  },
  {
    label: "RP3: 1日1回 夕食後",
    rows: [
      {
        name: "ロスバスタチン錠2.5mg",
        cells: [
          { kind: "med", name: "ロスバスタチン錠2.5mg", doseText: "1錠", qtyText: "14日分" },
          { kind: "med", name: "ロスバスタチン錠2.5mg", tone: "changed", tagLabel: "変更", doseText: "1錠", prevQtyText: "14日分", qtyText: "30日分" },
          { kind: "med", name: "ロスバスタチン錠2.5mg", tone: "unchanged", tagLabel: "継続", doseText: "1錠", qtyText: "30日分" },
        ],
      },
      {
        name: "マグミット錠330mg",
        cells: [
          { kind: "med", name: "マグミット錠330mg", doseText: "1錠", qtyText: "14日分" },
          { kind: "med", name: "マグミット錠330mg", tone: "changed", tagLabel: "変更", doseText: "1錠", prevQtyText: "14日分", qtyText: "30日分" },
          { kind: "med", name: "マグミット錠330mg", tone: "unchanged", tagLabel: "継続", doseText: "1錠", qtyText: "30日分" },
        ],
      },
      {
        name: "レバミピド錠100mg",
        cells: [
          { kind: "empty" },
          { kind: "empty" },
          { kind: "med", name: "レバミピド錠100mg", tone: "added", tagLabel: "新規", doseText: "1錠", qtyText: "30日分" },
        ],
      },
    ],
  },
  {
    label: "RP4: 1日3回 毎食後",
    rows: [
      {
        name: "クラリスロマイシン錠200mg",
        cells: [
          { kind: "empty" },
          { kind: "med", name: "クラリスロマイシン錠200mg", tone: "added", tagLabel: "新規", doseText: "1錠", qtyText: "3日分" },
          { kind: "discontinued", name: "クラリスロマイシン錠200mg", doseText: "1錠", qtyText: "3日分" },
        ],
      },
    ],
  },
  {
    label: "RP5: 頓用・疼痛時",
    rows: [
      {
        name: "ロキソニン錠60mg",
        cells: [
          { kind: "med", name: "ロキソニン錠60mg", doseText: "1錠", qtyText: "10回分" },
          { kind: "discontinued", name: "ロキソニン錠60mg", doseText: "1錠", qtyText: "10回分" },
          { kind: "empty" },
        ],
      },
    ],
  },
];

const DEMO_TIMELINE_VISITS = [
  {
    date: "2026-08-11",
    stepLabel: "今回",
    status: "下書き",
    rxNo: "RX-003",
    isLatest: true,
    rps: [
      { rp: "RP1: 1日1回 朝食後（30日分）", meds: ["アムロジピン錠5mg 2錠", "オルメサルタン錠20mg 1錠", "フォシーガ錠10mg 1錠", "タケキャブ錠10mg 1錠"] },
      { rp: "RP2: 1日2回 朝夕食後（30日分）", meds: ["メトホルミン塩酸塩錠250mg 2錠"] },
      { rp: "RP3: 1日1回 夕食後（30日分）", meds: ["ロスバスタチン錠2.5mg 1錠", "マグミット錠330mg 1錠", "レバミピド錠100mg 1錠"] },
    ],
    soap: [
      { label: "S", text: "めまい・ふらつきなし。胃部不快感もなく服用継続中。" },
      { label: "O", text: "血圧 128/78mmHg、HbA1c 7.4%、残薬なし。" },
      { label: "A", text: "血糖コントロール強化のためジャヌビア中止→フォシーガ新規・メトホルミン増量。" },
      { label: "P", text: "SGLT2阻害薬の水分摂取・尿路感染予防・低血糖対処を指導。" },
    ],
  },
  {
    date: "2026-07-22",
    stepLabel: "前回",
    status: "確定済み",
    rxNo: "RX-002",
    isLatest: false,
    rps: [
      { rp: "RP1: 1日1回 朝食後（30日分）", meds: ["アムロジピン錠5mg 2錠", "オルメサルタン錠20mg 1錠", "ジャヌビア錠50mg 1錠", "タケキャブ錠10mg 1錠"] },
      { rp: "RP2: 1日2回 朝夕食後（30日分）", meds: ["メトホルミン塩酸塩錠250mg 1錠"] },
      { rp: "RP3: 1日1回 夕食後（30日分）", meds: ["ロスバスタチン錠2.5mg 1錠", "マグミット錠330mg 1錠"] },
      { rp: "RP4: 1日3回 毎食後（3日分）", meds: ["クラリスロマイシン錠200mg 1錠"] },
    ],
    soap: [
      { label: "S", text: "咽頭痛あり耳鼻科にて抗菌薬追加。慢性疾患薬は30日分希望。" },
      { label: "O", text: "血圧 138/84mmHg。相互作用確認（ロスバスタチン併用注意モニタ）。" },
      { label: "A", text: "降圧目標未達のためアムロジピン増量、他継続処方も14日→30日へ延長。" },
      { label: "P", text: "過度の血圧低下に注意喚起し、抗菌薬3日分の飲み切りを指導。" },
    ],
  },
  {
    date: "2026-06-20",
    stepLabel: "2回前",
    status: "確定済み",
    rxNo: "RX-001",
    isLatest: false,
    rps: [
      { rp: "RP1: 1日1回 朝食後（14日分 / ジャヌビアのみ30日分）", meds: ["アムロジピン錠5mg 1錠", "オルメサルタン錠20mg 1錠", "ジャヌビア錠50mg 1錠", "タケキャブ錠10mg 1錠"] },
      { rp: "RP2: 1日2回 朝夕食後（14日分）", meds: ["メトホルミン塩酸塩錠250mg 1錠"] },
      { rp: "RP3: 1日1回 夕食後（14日分）", meds: ["ロスバスタチン錠2.5mg 1錠", "マグミット錠330mg 1錠"] },
      { rp: "RP5: 頓用・疼痛時（10回分）", meds: ["ロキソニン錠60mg 1錠"] },
    ],
    soap: [
      { label: "S", text: "お薬手帳持参あり。便通はマグミットで良好。腰痛時に頓用使用。" },
      { label: "O", text: "血圧 132/80mmHg、残薬なし。" },
      { label: "P", text: "胃薬（タケキャブ）継続とロキソニン空腹時回避を再確認。" },
    ],
  },
];

function PatientDetailThreePaneDemo({
  initialMode = "past_history",
}: {
  initialMode?: string;
}) {
  const [activeMode, setActiveMode] = useState(initialMode);
  const [selectedVisit, setSelectedVisit] = useState("2026-08-11");

  return (
    <StoreFrame
      storeName="丸の内中央薬局"
      identity="店舗スタッフ (操作)"
      navigation={
        <>
          <Link href="#">業務ホーム</Link>
          <Link href="#">患者一覧・検索</Link>
          <Link href="#">新規患者登録</Link>
          <Link href="#">店舗設定</Link>
          <Link href="#">マイ設定</Link>
          <Button variant="secondary" onAction={() => {}}>
            ログアウト
          </Button>
        </>
      }
    >
      <ThreePane
        left={
          <Stack gap="small">
            <Panel>
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: "8px",
                  paddingBottom: "8px",
                  marginBottom: "8px",
                  borderBottom: "1px solid #d0ddd8",
                }}
              >
                <div>
                  <Subheading>テスト 太郎</Subheading>
                  <div style={{ fontSize: "13px", color: "#4f6862" }}>
                    テスト タロウ
                  </div>
                </div>
                <Badge>有効</Badge>
              </div>
              <PropertyList>
                <PropertyRow label="患者番号" value="#1001" />
                <PropertyRow label="生年月日" value="1958-04-12 (68歳)" />
                <PropertyRow label="性別" value="男性" />
                <PropertyRow label="郵便番号" value="〒100-0005" />
                <PropertyRow label="住所" value="東京都千代田区丸の内1-1-1" />
                <PropertyRow label="電話番号" value="090-1234-5678" isLast />
              </PropertyList>
            </Panel>
            <Panel>
              <SectionHeading>臨床プロファイル（薬歴投影）</SectionHeading>
              <Stack gap="small">
                <CompactInfoCard title="アレルギー" tone="alert">
                  <span>ペニシリン系抗菌薬（全身発疹）</span>
                </CompactInfoCard>
                <CompactInfoCard title="副作用歴">
                  <span style={{ color: "#4f6862" }}>特記事項なし</span>
                </CompactInfoCard>
                <CompactInfoCard title="既往歴">
                  <span>本態性高血圧症 / 2型糖尿病 / 脂質異常症</span>
                </CompactInfoCard>
              </Stack>
            </Panel>
          </Stack>
        }
        center={
          activeMode === "patient_timeline" ? (
            <Panel>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "8px",
                  marginBottom: "10px",
                }}
              >
                <div>
                  <Subheading>患者タイムライン</Subheading>
                  <span style={{ fontSize: "13px", color: "#4f6862" }}>
                    来局・処方・薬歴の時系列経過（全 3 件 / 1処方 8薬剤）
                  </span>
                </div>
                <Link href="#" appearance="action">
                  ＋ 新規受付・処方登録
                </Link>
              </div>
              <TimelineList>
                {DEMO_TIMELINE_VISITS.map((v, idx) => (
                  <TimelineItem
                    key={v.rxNo}
                    dateLabel={v.date}
                    stepLabel={v.stepLabel}
                    selected={selectedVisit === v.date}
                    isLatest={v.isLatest}
                    isLast={idx === DEMO_TIMELINE_VISITS.length - 1}
                    badges={
                      <>
                        <Badge>調剤・服薬指導</Badge>
                        <Badge>{v.status}</Badge>
                      </>
                    }
                    institutionText={`丸の内中央クリニック（処方箋: ${v.rxNo}）`}
                    headerActions={
                      <Button
                        variant={selectedVisit === v.date ? "primary" : "secondary"}
                        onAction={() => setSelectedVisit(v.date)}
                      >
                        {selectedVisit === v.date ? "編集中" : "右欄で開く"}
                      </Button>
                    }
                    prescriptionContent={
                      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                        {v.rps.map((rp) => (
                          <div key={rp.rp}>
                            <div style={{ fontSize: "11px", color: "#4f6862", fontWeight: 600 }}>
                              {rp.rp}
                            </div>
                            <ul style={{ margin: "1px 0 0 16px", padding: 0, fontSize: "12px" }}>
                              {rp.meds.map((m) => (
                                <li key={m}>{m}</li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    }
                    soapContent={
                      <div style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "12px" }}>
                        {v.soap.map((s) => (
                          <p key={s.label} style={{ margin: 0 }}>
                            <strong>{s.label}:</strong> {s.text}
                          </p>
                        ))}
                      </div>
                    }
                  />
                ))}
              </TimelineList>
            </Panel>
          ) : activeMode === "usage_history" ? (
            <Panel>
              <Subheading>使用薬剤履歴</Subheading>
              <Table aria-label="使用薬剤履歴">
                <thead>
                  <tr>
                    <TableHeader>薬剤名</TableHeader>
                    <TableHeader>最新用法</TableHeader>
                    <TableHeader>累計日数</TableHeader>
                    <TableHeader>処方回数</TableHeader>
                    <TableHeader>最終処方日</TableHeader>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <TableCell>アムロジピン錠5mg</TableCell>
                    <TableCell>1日1回 朝食後</TableCell>
                    <TableCell>74日</TableCell>
                    <TableCell>3回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>オルメサルタン錠20mg</TableCell>
                    <TableCell>1日1回 朝食後</TableCell>
                    <TableCell>74日</TableCell>
                    <TableCell>3回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>タケキャブ錠10mg</TableCell>
                    <TableCell>1日1回 朝食後</TableCell>
                    <TableCell>74日</TableCell>
                    <TableCell>3回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>メトホルミン塩酸塩錠250mg</TableCell>
                    <TableCell>1日2回 朝夕食後</TableCell>
                    <TableCell>74日</TableCell>
                    <TableCell>3回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>ロスバスタチン錠2.5mg</TableCell>
                    <TableCell>1日1回 夕食後</TableCell>
                    <TableCell>74日</TableCell>
                    <TableCell>3回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>マグミット錠330mg</TableCell>
                    <TableCell>1日1回 夕食後</TableCell>
                    <TableCell>74日</TableCell>
                    <TableCell>3回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>フォシーガ錠10mg</TableCell>
                    <TableCell>1日1回 朝食後</TableCell>
                    <TableCell>30日</TableCell>
                    <TableCell>1回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                  <tr>
                    <TableCell>レバミピド錠100mg</TableCell>
                    <TableCell>1日1回 夕食後</TableCell>
                    <TableCell>30日</TableCell>
                    <TableCell>1回</TableCell>
                    <TableCell>2026-08-11</TableCell>
                  </tr>
                </tbody>
              </Table>
            </Panel>
          ) : (
            <Panel>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "8px",
                  marginBottom: "8px",
                }}
              >
                <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
                  <Subheading>過去の処方・薬歴（直近3回比較）</Subheading>
                  <span style={{ fontSize: "13px", color: "#4f6862" }}>
                    全 3 件（各回 8薬剤）
                  </span>
                </div>
                <Link href="#" appearance="action">
                  ＋ 新規受付・処方登録
                </Link>
              </div>

              <ContrastSummaryBanner hasChanges>
                <span>前回からの変更:</span>
                <ContrastStatusTag tone="changed">用量・日数変更 1剤</ContrastStatusTag>
                <ContrastStatusTag tone="added">新規追加 2剤</ContrastStatusTag>
                <ContrastStatusTag tone="discontinued">終了 2剤</ContrastStatusTag>
              </ContrastSummaryBanner>

              <ContrastMatrixFrame>
                <ContrastMatrixRow>
                  <ContrastHeaderCell>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <ContrastStatusTag tone="slot">2回前</ContrastStatusTag>
                        <strong style={{ fontSize: "13px" }}>2026-06-20</strong>
                      </div>
                      <Badge>確定済み</Badge>
                    </div>
                    <div style={{ fontSize: "12px", color: "#4f6862" }}>
                      丸の内中央クリニック（RX-001 / 8剤）
                    </div>
                  </ContrastHeaderCell>
                  <ContrastHeaderCell>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <ContrastStatusTag tone="slot">前回</ContrastStatusTag>
                        <strong style={{ fontSize: "13px" }}>2026-07-22</strong>
                      </div>
                      <Badge>確定済み</Badge>
                    </div>
                    <div style={{ fontSize: "12px", color: "#4f6862" }}>
                      丸の内中央クリニック（RX-002 / 8剤）
                    </div>
                  </ContrastHeaderCell>
                  <ContrastHeaderCell selected>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <ContrastStatusTag tone="slot">今回</ContrastStatusTag>
                        <strong style={{ fontSize: "13px" }}>2026-08-11</strong>
                      </div>
                      <Badge>下書き</Badge>
                    </div>
                    <div style={{ fontSize: "12px", color: "#4f6862" }}>
                      丸の内中央クリニック（RX-003 / 8剤）
                    </div>
                  </ContrastHeaderCell>
                </ContrastMatrixRow>

                {DEMO_GROUPS.map((group) => (
                  <div key={group.label}>
                    <ContrastSectionBar>{group.label}</ContrastSectionBar>
                    {group.rows.map((row) => (
                      <ContrastMatrixRow key={row.name} bordered>
                        {row.cells.map((cell, colIdx) => (
                          <ContrastCell
                            key={`${row.name}-${colIdx}`}
                            selected={colIdx === 2}
                          >
                            {cell.kind === "empty" ? (
                              <span style={{ fontSize: "12px", color: "#4f6862" }}>—</span>
                            ) : cell.kind === "discontinued" ? (
                              <div>
                                <div style={{ display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap" }}>
                                  <ContrastStatusTag tone="discontinued">
                                    終了（前回あり）
                                  </ContrastStatusTag>
                                  <span style={{ fontSize: "12px", color: "#4f6862", textDecoration: "line-through" }}>
                                    {cell.name}
                                  </span>
                                </div>
                                <div style={{ fontSize: "11px", color: "#4f6862" }}>
                                  前回: {cell.doseText} ・ {cell.qtyText}
                                </div>
                              </div>
                            ) : (
                              <>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "4px" }}>
                                  <span style={{ fontSize: "13px", fontWeight: 600 }}>
                                    {cell.name}
                                  </span>
                                  {cell.tone && cell.tagLabel ? (
                                    <ContrastStatusTag tone={cell.tone}>
                                      {cell.tagLabel}
                                    </ContrastStatusTag>
                                  ) : null}
                                </div>
                                <div style={{ fontSize: "12px", color: "#4f6862" }}>
                                  {cell.prevDoseText ? (
                                    <ContrastDiffText>
                                      {cell.prevDoseText} → {cell.doseText}
                                    </ContrastDiffText>
                                  ) : (
                                    <span>{cell.doseText}</span>
                                  )}
                                  {" ・ "}
                                  {cell.prevQtyText ? (
                                    <ContrastDiffText>
                                      {cell.prevQtyText} → {cell.qtyText}
                                    </ContrastDiffText>
                                  ) : (
                                    <span>{cell.qtyText}</span>
                                  )}
                                </div>
                              </>
                            )}
                          </ContrastCell>
                        ))}
                      </ContrastMatrixRow>
                    ))}
                  </div>
                ))}

                <ContrastSectionBar>薬歴（SOAP要約）</ContrastSectionBar>
                <ContrastMatrixRow>
                  <ContrastCell>
                    <p style={{ margin: 0, fontSize: "12px" }}>
                      <strong>S:</strong> お薬手帳持参。便通良好。
                    </p>
                    <p style={{ margin: 0, fontSize: "12px" }}>
                      <strong>P:</strong> 胃薬継続・頓用空腹時回避を確認。
                    </p>
                  </ContrastCell>
                  <ContrastCell>
                    <p style={{ margin: 0, fontSize: "12px" }}>
                      <strong>A:</strong> 血圧高めのためアムロジピン増量、他30日へ。
                    </p>
                    <p style={{ margin: 0, fontSize: "12px" }}>
                      <strong>P:</strong> 抗菌薬飲み切り指導。
                    </p>
                  </ContrastCell>
                  <ContrastCell selected>
                    <p style={{ margin: 0, fontSize: "12px" }}>
                      <strong>S:</strong> めまい・胃部不快感なし。
                    </p>
                    <p style={{ margin: 0, fontSize: "12px" }}>
                      <strong>O:</strong> 血圧 128/78mmHg、HbA1c 7.4%
                    </p>
                  </ContrastCell>
                </ContrastMatrixRow>
              </ContrastMatrixFrame>
            </Panel>
          )
        }
        right={
          <Panel>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <SectionHeading>薬歴ブロック編集（動的区分＋文章方式）</SectionHeading>
              <Badge>下書き</Badge>
            </div>
            <Stack gap="small">
              <div style={{ border: "1px solid #d0ddd8", borderRadius: "8px", padding: "8px", background: "#f8faf9" }}>
                <Badge>S</Badge>
                <TextArea aria-label="S（主観的情報）の記載本文" rows={2} defaultValue="めまい・ふらつきなし。胃部不快感もなく朝食後・夕食後ともに規則正しく服用中。" />
              </div>
              <div style={{ border: "1px solid #d0ddd8", borderRadius: "8px", padding: "8px", background: "#f8faf9" }}>
                <Badge>O</Badge>
                <TextArea aria-label="O（客観的情報）の記載本文" rows={2} defaultValue="血圧 128/78mmHg、HbA1c 7.4%、残薬なし。" />
              </div>
              <div style={{ border: "1px solid #d0ddd8", borderRadius: "8px", padding: "8px", background: "#f8faf9" }}>
                <Badge>A</Badge>
                <TextArea aria-label="A（評価・判断）の記載本文" rows={2} defaultValue="血糖コントロール強化のためジャヌビア中止→フォシーガ新規・メトホルミン増量。胃粘膜保護にレバミピド追加。" />
              </div>
              <div style={{ border: "1px solid #d0ddd8", borderRadius: "8px", padding: "8px", background: "#f8faf9" }}>
                <Badge>P</Badge>
                <TextArea aria-label="P（計画）の記載本文" rows={2} defaultValue="フォシーガ開始に伴うこまめな水分摂取・尿路感染予防・低血糖対処およびメトホルミン増量後の消化器症状注意を説明。" />
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="primary" onAction={() => {}}>
                  下書き保存
                </Button>
              </div>
            </Stack>
          </Panel>
        }
        footer={
          <DetailFooterBar
            items={[
              { id: "past_history", label: "過去処方（固定3列）" },
              { id: "patient_timeline", label: "患者タイムライン" },
              { id: "usage_history", label: "使用薬剤履歴" },
              { id: "patient_summary", label: "患者サマリー" },
            ]}
            activeId={activeMode}
            onSelect={setActiveMode}
          />
        }
      />
    </StoreFrame>
  );
}

export const Default: Story = {
  args: {
    left: null,
    center: null,
    right: null,
  },
  render: () => <PatientDetailThreePaneDemo initialMode="past_history" />,
};

export const TimelineMode: Story = {
  args: {
    left: null,
    center: null,
    right: null,
  },
  render: () => <PatientDetailThreePaneDemo initialMode="patient_timeline" />,
};
