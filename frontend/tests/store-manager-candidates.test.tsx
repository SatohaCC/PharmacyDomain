import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { StoreDetailView } from "../src/features/stores/ui/store-detail-view";
import type { StoreDetail } from "../src/features/stores/model/store";

const baseStore: StoreDetail = {
  id: "store-1",
  corporate_id: "corp-1",
  name: "テスト薬局",
  name_kana: "テストヤッキョク",
  name_romaji: null,
  postal_code: "1000001",
  address: "東京都千代田区1-1",
  phone_number: "0312345678",
  fax_number: null,
  email: null,
  code: "ST-1",
  insurance_pharmacy_number: null,
  status: "active",
};

const staffUsers = [
  {
    id: "u-active-pharmacist",
    person_id: "p-1",
    role: "store_operator",
    status: "active",
    account_status: "active",
    staff_id: "s-active-pharmacist",
    staff_name: "有効 薬剤師",
  },
  {
    id: "u-second-pharmacist",
    person_id: "p-2",
    role: "store_operator",
    status: "active",
    account_status: "active",
    staff_id: "s-second-pharmacist",
    staff_name: "後任 薬剤師",
  },
  {
    id: "u-clerk",
    person_id: "p-3",
    role: "store_operator",
    status: "active",
    account_status: "active",
    staff_id: "s-clerk",
    staff_name: "調剤 事務",
  },
  {
    id: "u-suspended",
    person_id: "p-4",
    role: "store_operator",
    status: "suspended",
    account_status: "active",
    staff_id: "s-suspended",
    staff_name: "停止 薬剤師",
  },
  {
    id: "u-retired",
    person_id: "p-5",
    role: "store_operator",
    status: "active",
    account_status: "active",
    staff_id: "s-retired",
    staff_name: "退職 薬剤師",
  },
];

const staffs = [
  {
    id: "s-active-pharmacist",
    last_name: "有効",
    first_name: "薬剤師",
    code: "P01",
    is_active: true,
    is_pharmacist: true,
    status: "active",
  },
  {
    id: "s-second-pharmacist",
    last_name: "後任",
    first_name: "薬剤師",
    code: null,
    is_active: true,
    is_pharmacist: true,
    status: "active",
  },
  {
    id: "s-clerk",
    last_name: "調剤",
    first_name: "事務",
    code: "C01",
    is_active: true,
    is_pharmacist: false,
    status: "active",
  },
  {
    id: "s-suspended",
    last_name: "停止",
    first_name: "薬剤師",
    code: null,
    is_active: true,
    is_pharmacist: true,
    status: "active",
  },
  {
    id: "s-retired",
    last_name: "退職",
    first_name: "薬剤師",
    code: null,
    is_active: false,
    is_pharmacist: true,
    status: "retired",
  },
  {
    id: "s-other-store",
    last_name: "他店",
    first_name: "薬剤師",
    code: null,
    is_active: true,
    is_pharmacist: true,
    status: "active",
  },
];

const noop = async () => {};

it("管理薬剤師の任命セレクトボックスには現在有効で所属している薬剤師だけが表示される", async () => {
  const user = userEvent.setup();
  render(
    <StoreDetailView
      store={baseStore}
      corporateId="corp-1"
      managers={[]}
      staffUsers={staffUsers}
      staffs={staffs}
      onUpdateBasic={noop}
      onUpdateAddress={noop}
      onUpdateContact={noop}
      onAppointStoreManager={noop}
      onChangeStatus={noop}
    />,
  );

  await user.click(screen.getByRole("button", { name: "管理薬剤師を任命" }));
  await user.click(screen.getByRole("button", { name: /任命する薬剤師/ }));

  const options = screen.getAllByRole("option").map((el) => el.textContent);
  expect(options).toEqual(["有効 薬剤師（P01）", "後任 薬剤師"]);
});

it("管理薬剤師の交代セレクトボックスからは現在の管理薬剤師が除外される", async () => {
  const user = userEvent.setup();
  render(
    <StoreDetailView
      store={baseStore}
      corporateId="corp-1"
      managers={[
        {
          id: "mgr-1",
          staff_id: "s-active-pharmacist",
          starts_on: "2026-01-01",
          ends_on: null,
          status: "active",
        },
      ]}
      staffUsers={staffUsers}
      staffs={staffs}
      onUpdateBasic={noop}
      onUpdateAddress={noop}
      onUpdateContact={noop}
      onReplaceStoreManager={noop}
      onChangeStatus={noop}
    />,
  );

  expect(screen.getByText(/有効 薬剤師（任命日: 2026-01-01）/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "交代する" }));
  await user.click(screen.getByRole("button", { name: /後任薬剤師/ }));

  const options = screen.getAllByRole("option").map((el) => el.textContent);
  expect(options).toEqual(["後任 薬剤師"]);
});
