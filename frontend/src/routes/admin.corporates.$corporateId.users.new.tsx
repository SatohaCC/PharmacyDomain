import { createFileRoute, Link } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { api, result, corporationParams } from "../shared/api/client";
import {
  prepareInvitation,
  type RegistrationProgress,
} from "../features/users/registration";
import { Field, Form, text } from "../shared/ui/common";
export const Route = createFileRoute(
  "/admin/corporates/$corporateId/users/new",
)({
  loader: async ({ params, abortController }) => {
    const options = {
      params: corporationParams(params.corporateId),
      signal: abortController.signal,
    };
    const [stores, staffs] = await Promise.all([
      result(api.GET("/corporates/{corporate_id}/stores", options)),
      result(api.GET("/corporates/{corporate_id}/staffs", options)),
    ]);
    return { stores, staffs };
  },
  component: Invite,
});
function Invite() {
  const { corporateId } = Route.useParams();
  const { stores, staffs } = Route.useLoaderData();
  const [personMode, setPersonMode] = useState("new");
  const [role, setRole] = useState<
    "corporate_admin" | "store_operator" | "store_viewer"
  >("corporate_admin");
  const [staffMode, setStaffMode] = useState("existing");
  const progress = useRef<RegistrationProgress>({});
  const [snapshot, setSnapshot] = useState<RegistrationProgress>({});
  const changed = () => setSnapshot({ ...progress.current });
  const [issued, setIssued] = useState<{ id: string; secret: string }>();
  const [status, setStatus] = useState("");
  const [copied, setCopied] = useState(false);
  const [frozen, setFrozen] = useState(false);
  const params = corporationParams(corporateId);
  if (issued)
    return (
      <section>
        <h2>招待を発行しました</h2>
        <p>
          本人の受諾後にユーザー登録が完了します。メールは自動送信されません。
        </p>
        <p>
          招待ID: <code>{issued.id}</code>
        </p>
        <label className="field">
          招待URL（この画面を離れると再表示できません）
          <textarea
            readOnly
            value={
              location.origin +
              "/invitations/accept#secret=" +
              encodeURIComponent(issued.secret)
            }
          />
        </label>
        <button
          onClick={async () => {
            await navigator.clipboard.writeText(
              location.origin +
                "/invitations/accept#secret=" +
                encodeURIComponent(issued.secret),
            );
            setCopied(true);
          }}
        >
          招待URLをコピー
        </button>
        {copied && <p role="status">コピーしました。</p>}
        <Form
          label="受諾状態を確認"
          onSubmit={async () => {
            const detail = await result(
              api.GET(
                "/corporates/{corporate_id}/user-invitations/{invitation_id}",
                {
                  params: {
                    path: {
                      corporate_id: corporateId,
                      invitation_id: issued.id,
                    },
                  },
                },
              ),
            );
            setStatus(detail.status);
          }}
        />
        {status && (
          <p role="status">
            招待状態:{" "}
            {status === "accepted"
              ? "受諾済み"
              : status === "cancelled"
                ? "取消済み"
                : "未受諾"}
          </p>
        )}
        <Link
          to="/admin/corporates/$corporateId/users"
          params={{ corporateId }}
        >
          ユーザー一覧へ
        </Link>
      </section>
    );
  return (
    <section>
      <h2>ユーザー登録・招待</h2>
      <p>
        本人を登録し、法人の利用権限を招待します。パスワードは設定しません。
      </p>
      {snapshot.personId && (
        <p className="notice">
          本人登録済み: <code>{snapshot.personId}</code>
          {snapshot.staffId && (
            <>
              {" "}
              ／スタッフ: <code>{snapshot.staffId}</code>
            </>
          )}
          {snapshot.linked && " ／本人紐付け済み"}
          。この段階から招待を再試行します。
        </p>
      )}
      {snapshot.uncertain && (
        <p role="alert">
          前回の処理結果が不明です。重複登録を避けるため再送を止めています。管理者へ確認してください。
        </p>
      )}
      <Form
        label="招待を発行する"
        onSubmit={async (d) => {
          const p = progress.current;
          const expires = new Date(text(d, "expires_at"));
          if (!Number.isFinite(expires.valueOf()) || expires <= new Date())
            throw new Error("招待期限は未来日時を指定してください。");
          if (personMode === "existing" && !p.personId) {
            p.personId = text(d, "person_id");
            if (!p.personId) throw new Error("本人IDを指定してください。");
          }
          const storeIds = d.getAll("store_ids").map(String);
          if (role !== "corporate_admin" && !storeIds.length)
            throw new Error("許可する店舗を選択してください。");
          setFrozen(true);
          const names = {
            last_name: text(d, "last_name"),
            first_name: text(d, "first_name"),
            last_name_kana: text(d, "last_name_kana"),
            first_name_kana: text(d, "first_name_kana"),
          };
          const prepared = await prepareInvitation(
            p,
            {
              createPerson: async () =>
                (
                  await result(
                    api.POST("/corporates/{corporate_id}/people", {
                      params,
                      body: names,
                    }),
                  )
                ).id,
              prepareStaff:
                role === "corporate_admin"
                  ? undefined
                  : async (personId) => {
                      if (staffMode === "existing" && !p.linked) {
                        p.staffId = text(d, "staff_id");
                        changed();
                      }
                      if (!p.staffId) {
                        if (staffMode === "existing") {
                          p.staffId = text(d, "staff_id");
                          if (!p.staffId)
                            throw new Error("スタッフを選択してください。");
                        } else {
                          p.staffId = (
                            await result(
                              api.POST("/corporates/{corporate_id}/staffs", {
                                params,
                                body: {
                                  ...names,
                                  is_registered_dietitian: true,
                                  initial_home_store_id: text(d, "home_store"),
                                  initial_start_date: text(d, "start_date"),
                                },
                              }),
                            )
                          ).id;
                        }
                        changed();
                      }
                      if (!p.staffId)
                        throw new Error("スタッフを指定してください。");
                      if (!p.linked) {
                        await result(
                          api.POST(
                            "/corporates/{corporate_id}/staffs/{staff_id}/person-link",
                            {
                              params: {
                                path: {
                                  corporate_id: corporateId,
                                  staff_id: p.staffId,
                                },
                              },
                              body: { person_id: personId },
                            },
                          ),
                        );
                        p.linked = true;
                        changed();
                      }
                    },
              invite: (personId) =>
                result(
                  api.POST("/corporates/{corporate_id}/user-invitations", {
                    params,
                    body: {
                      person_id: personId,
                      addressee: text(d, "addressee"),
                      role,
                      expires_at: expires.toISOString(),
                      store_ids: storeIds,
                      staff_id: role === "corporate_admin" ? null : p.staffId,
                    },
                  }),
                ),
            },
            changed,
          );
          setIssued(prepared);
        }}
      >
        <h3>1. 本人情報</h3>
        <label className="field">
          本人の指定
          <select
            value={personMode}
            disabled={frozen}
            onChange={(e) => setPersonMode(e.target.value)}
          >
            <option value="new">新しく本人を登録</option>
            <option value="existing">登録済みの本人IDを指定</option>
          </select>
        </label>
        {personMode === "existing" ? (
          <Field
            name="person_id"
            label="本人ID"
            required
            readOnly={!!snapshot.personId}
          />
        ) : null}
        {(personMode === "new" ||
          (role !== "corporate_admin" && staffMode === "new")) && (
          <div className="grid">
            {[
              ["last_name", "姓"],
              ["first_name", "名"],
              ["last_name_kana", "姓カナ"],
              ["first_name_kana", "名カナ"],
            ].map(([name, label]) => (
              <Field
                key={name}
                name={name}
                label={label}
                required
                readOnly={!!snapshot.personId}
              />
            ))}
          </div>
        )}
        <h3>2. 法人での権限</h3>
        <label className="field">
          ロール
          <select
            value={role}
            disabled={frozen}
            onChange={(e) => setRole(e.target.value as typeof role)}
          >
            <option value="corporate_admin">法人管理者</option>
            <option value="store_operator">店舗操作者</option>
            <option value="store_viewer">店舗閲覧者</option>
          </select>
        </label>
        {role !== "corporate_admin" && (
          <>
            <div className="field">
              許可する店舗
              {stores.map((s) => (
                <label className="check" key={s.id}>
                  <input type="checkbox" name="store_ids" value={s.id} />
                  {s.name}
                </label>
              ))}
              {!stores.length && <p>先に店舗を登録してください。</p>}
            </div>
            <label className="field">
              スタッフの指定
              <select
                disabled={frozen}
                value={staffMode}
                onChange={(e) => setStaffMode(e.target.value)}
              >
                <option value="existing">既存スタッフを選択</option>
                <option value="new">スタッフを新規登録</option>
              </select>
            </label>
            {staffMode === "existing" ? (
              <label className="field">
                スタッフ
                <select
                  name="staff_id"
                  required
                  defaultValue=""
                  disabled={!!snapshot.linked}
                >
                  <option value="">選択してください</option>
                  {staffs
                    .filter((s) => s.is_active)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.last_name} {s.first_name}
                      </option>
                    ))}
                </select>
              </label>
            ) : (
              <>
                <label className="field">
                  主所属店舗
                  <select name="home_store" required defaultValue="">
                    <option value="">選択してください</option>
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
                <Field
                  name="start_date"
                  label="所属開始日"
                  type="date"
                  required
                />
              </>
            )}
          </>
        )}
        <h3>3. 招待</h3>
        <Field
          name="addressee"
          label="宛先メールアドレス"
          type="email"
          required
        />
        <Field
          name="expires_at"
          label="招待期限（端末の現地時刻）"
          type="datetime-local"
          required
        />
        <p>
          登録は段階ごとに保存されます。途中で閉じた場合、作成済みの本人をこの画面から検索・復元することはできません。
        </p>
      </Form>
    </section>
  );
}
