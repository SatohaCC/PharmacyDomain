export interface paths {
  "/contracts": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Register Contract
     * @description ベンダーが法人・初期管理者・資格情報を一括登録する。
     */
    post: operations["register_contract_contracts_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/users/{membership_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get User
     * @description 自法人のユーザー権限を取得する。
     */
    get: operations["get_user_corporates__corporate_id__users__membership_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Membership
     * @description 法人アクセス権を変更する。個人アカウントの所有者は変えない。
     */
    patch: operations["change_membership_corporates__corporate_id__users__membership_id__patch"];
    trace?: never;
  };
  "/accounts/{account_id}/suspension": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Suspend Account
     * @description ベンダーまたは自法人の管理者が個人アカウント全体を停止する。
     */
    post: operations["suspend_account_accounts__account_id__suspension_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Me
     * @description 現在有効な本人・アカウント・法人アクセス範囲を返す。
     */
    get: operations["get_me_me_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/me/stores": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get My Stores
     * @description 現在選択可能な店舗一覧（有効Membership許可店舗と当日Staff所属の積集合）を返す。
     */
    get: operations["get_my_stores_me_stores_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/users": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Users
     * @description 自法人のユーザー権限を一覧する。
     */
    get: operations["list_users_corporates__corporate_id__users_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/users/{membership_id}/suspension": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Suspend Membership
     * @description 法人のアクセス権だけを停止する。
     */
    post: operations["suspend_membership_corporates__corporate_id__users__membership_id__suspension_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/users/{membership_id}/reactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reactivate Membership
     * @description 本人・スタッフの有効性を再確認して権限を再開する。
     */
    post: operations["reactivate_membership_corporates__corporate_id__users__membership_id__reactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/users/{membership_id}/staff-registration": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Register Staff For Admin
     * @description 初期管理者にスタッフを紐付ける。
     */
    post: operations["register_staff_for_admin_corporates__corporate_id__users__membership_id__staff_registration_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/people": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Register Person
     * @description 自法人の本人を登録する。
     */
    post: operations["register_person_corporates__corporate_id__people_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/person-link": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Link Staff Person
     * @description スタッフと本人を変更不能な対応として登録する。
     */
    post: operations["link_staff_person_corporates__corporate_id__staffs__staff_id__person_link_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/accounts/{account_id}/reactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reactivate Account
     * @description 個人アカウント全体をベンダーが再開する。
     */
    post: operations["reactivate_account_accounts__account_id__reactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Login
     * @description 初期パスワードでは変更専用セッションを返す。
     */
    post: operations["login_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/vendor/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Vendor Login
     * @description 運営者の資格情報を照合しセッションを発行する。
     */
    post: operations["vendor_login_auth_vendor_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/password": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Change Password
     * @description 既存セッションを失効して変更後のセッションを返す。
     */
    post: operations["change_password_auth_password_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/store-context": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Select Store Context
     * @description 許可・所属済みの店舗を選択した新しいセッションを発行する。
     */
    post: operations["select_store_context_auth_store_context_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/auth/logout": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Logout
     * @description サーバー上のセッションを削除する。
     */
    post: operations["logout_auth_logout_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/health": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Check Health
     * @description プロセスが応答できることだけを返す。
     *
     *     DBへは触らない。接続不能を含めた依存の健全性は、業務エンドポイントの
     *     結果と監視側で判断する。
     */
    get: operations["check_health_health_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Corporates
     * @description ベンダーが名称・状態で法人を検索する。
     */
    get: operations["list_corporates_corporates_get"];
    put?: never;
    /**
     * Register Corporate
     * @description 法人を新規登録する。
     */
    post: operations["register_corporate_corporates_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Corporate
     * @description 法人を1件取得する。
     */
    get: operations["get_corporate_corporates__corporate_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/name": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Corporate Name
     * @description 法人名を変更する。
     */
    patch: operations["change_corporate_name_corporates__corporate_id__name_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/representative": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Representative
     * @description 代表者名を変更する。
     */
    patch: operations["change_representative_corporates__corporate_id__representative_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/status": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Corporate Status
     * @description 法人の利用状態を変更する（ベンダーシステム管理者専用）。
     */
    patch: operations["change_corporate_status_corporates__corporate_id__status_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/policy": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Corporate Policy
     * @description 法人ポリシーを更新する。
     */
    put: operations["update_corporate_policy_corporates__corporate_id__policy_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Stores
     * @description 法人に所属する店舗を一覧する。
     */
    get: operations["list_stores_corporates__corporate_id__stores_get"];
    put?: never;
    /**
     * Register Store
     * @description 店舗を新規登録する。
     */
    post: operations["register_store_corporates__corporate_id__stores_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Store
     * @description 店舗を1件取得する。
     */
    get: operations["get_store_corporates__corporate_id__stores__store_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/names": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Store Names
     * @description 店舗名を変更する。
     */
    patch: operations["change_store_names_corporates__corporate_id__stores__store_id__names_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/code": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Store Code
     * @description 店舗コードを変更または解除する。
     */
    patch: operations["change_store_code_corporates__corporate_id__stores__store_id__code_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/address": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Store Address
     * @description 店舗所在地を変更する。
     */
    patch: operations["change_store_address_corporates__corporate_id__stores__store_id__address_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/licenses": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Store Licenses
     * @description 店舗の薬局開設許可および麻薬小売業者免許を更新する。
     */
    put: operations["update_store_licenses_corporates__corporate_id__stores__store_id__licenses_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/policy": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Store Policy
     * @description 店舗ポリシーを更新する。
     */
    put: operations["update_store_policy_corporates__corporate_id__stores__store_id__policy_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/effective-policy": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Effective Policy
     * @description 店舗の実効ポリシーを取得する。
     */
    get: operations["get_effective_policy_corporates__corporate_id__stores__store_id__effective_policy_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/contact-info": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Store Contact Info
     * @description 店舗連絡先を変更する。
     */
    patch: operations["change_store_contact_info_corporates__corporate_id__stores__store_id__contact_info_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/insurance-pharmacy-number": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Insurance Pharmacy Number
     * @description 保険薬局指定番号を変更または解除する。
     */
    patch: operations["change_insurance_pharmacy_number_corporates__corporate_id__stores__store_id__insurance_pharmacy_number_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/suspension": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Suspend Store
     * @description 店舗を休止する。
     */
    post: operations["suspend_store_corporates__corporate_id__stores__store_id__suspension_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/resumption": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Resume Store
     * @description 休止した店舗を再開する。
     */
    post: operations["resume_store_corporates__corporate_id__stores__store_id__resumption_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/closure": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Close Store
     * @description 残業務を確認して店舗を閉局する。
     */
    post: operations["close_store_corporates__corporate_id__stores__store_id__closure_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/closure-revocation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Revoke Store Closure
     * @description 誤って登録された閉局を取り消し、休止へ戻す（ベンダー専用）。
     *
     *     閉局と対称な「再開」にはしない。閉局で管理薬剤師の任命は終了しているので、
     *     有効へ戻すと管理薬剤師のいない店舗が業務を受けられる状態になる。
     */
    post: operations["revoke_store_closure_corporates__corporate_id__stores__store_id__closure_revocation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/business-hours": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Change Business Hours
     * @description 開局時間をまとめて置き換える。
     *
     *     部分更新にしない。週次の予定は全曜日が揃って初めて意味を持つので、曜日を
     *     1つだけ差し替えられると、残りの曜日がいつ登録されたものか分からなくなる。
     */
    put: operations["change_business_hours_corporates__corporate_id__stores__store_id__business_hours_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/opening-status": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Opening Status
     * @description 指定日時に開局しているかを返す。
     *
     *     未登録は「開いている」にも「閉じている」にも倒さず ``unknown`` を返す。
     */
    get: operations["get_opening_status_corporates__corporate_id__stores__store_id__opening_status_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/status-history": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Status History
     * @description 店舗状態の履歴を取得する。
     */
    get: operations["get_status_history_corporates__corporate_id__stores__store_id__status_history_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/manager-assignments": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Managers
     * @description 指定日の管理薬剤師または任命履歴を取得する。
     */
    get: operations["list_managers_corporates__corporate_id__stores__store_id__manager_assignments_get"];
    put?: never;
    /**
     * Manage Manager
     * @description 管理薬剤師を任命・交代・取消・終了する。
     */
    post: operations["manage_manager_corporates__corporate_id__stores__store_id__manager_assignments_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/manager-assignments/{assignment_id}/ending": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * End Manager
     * @description 管理薬剤師の任命期間を終了する。
     */
    post: operations["end_manager_corporates__corporate_id__stores__store_id__manager_assignments__assignment_id__ending_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/manager-assignments/{assignment_id}/cancellation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Cancel Manager
     * @description 開始前の任命を取消し履歴を残す。
     */
    post: operations["cancel_manager_corporates__corporate_id__stores__store_id__manager_assignments__assignment_id__cancellation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/manager-replacement": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Replace Manager
     * @description 旧任命の終了と新任命を同時に確定する。
     */
    post: operations["replace_manager_corporates__corporate_id__stores__store_id__manager_replacement_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Staffs
     * @description 法人に所属するスタッフを一覧する。
     */
    get: operations["list_staffs_corporates__corporate_id__staffs_get"];
    put?: never;
    /**
     * Register Staff
     * @description スタッフおよびアカウントを新規一括登録する。
     */
    post: operations["register_staff_corporates__corporate_id__staffs_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Staff
     * @description スタッフを1件取得する。
     */
    get: operations["get_staff_corporates__corporate_id__staffs__staff_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/names": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Staff Names
     * @description 氏名を変更する。
     */
    patch: operations["change_staff_names_corporates__corporate_id__staffs__staff_id__names_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/job-title": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Staff Job Title
     * @description 役職を変更または解除する。
     */
    patch: operations["change_staff_job_title_corporates__corporate_id__staffs__staff_id__job_title_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/qualifications": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Staff Qualifications
     * @description 資格を差し替える。
     *
     *     PATCH ではなく PUT なのは、送られた内容で資格一式を置き換えるからである。
     *     省いた項目は「変更しない」ではなく「その資格を持たない」になる。
     */
    put: operations["update_staff_qualifications_corporates__corporate_id__staffs__staff_id__qualifications_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/home-store": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Transfer Home Store
     * @description 主所属店舗を異動する。
     */
    patch: operations["transfer_home_store_corporates__corporate_id__staffs__staff_id__home_store_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/concurrent-stores": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Assign Concurrent Store
     * @description 兼務店舗を追加する。
     */
    post: operations["assign_concurrent_store_corporates__corporate_id__staffs__staff_id__concurrent_stores_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/concurrent-stores/{store_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /**
     * Remove Concurrent Store
     * @description 兼務店舗の期間を終了する。
     *
     *     終了日をクエリで受け取る。本文つきの ``DELETE`` は経路によって落とされる
     *     ことがあり、期間の指定が黙って消える。
     */
    delete: operations["remove_concurrent_store_corporates__corporate_id__staffs__staff_id__concurrent_stores__store_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/retirement": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Retire Staff
     * @description 退職させ、退職日以降に及ぶ所属をその日で打ち切る。
     */
    post: operations["retire_staff_corporates__corporate_id__staffs__staff_id__retirement_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/staffs/{staff_id}/reactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reactivate Staff
     * @description 在籍状態へ戻す。**所属は復元しない**ので、必要なら別途配属する。
     */
    post: operations["reactivate_staff_corporates__corporate_id__staffs__staff_id__reactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Register Patient
     * @description 患者を新規登録する。
     */
    post: operations["register_patient_corporates__corporate_id__patients_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Patient
     * @description 患者を1件取得する。
     */
    get: operations["get_patient_corporates__corporate_id__patients__patient_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/heading": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Patient Heading
     * @description 患者頭書きの現在値と変更履歴を取得する。
     */
    get: operations["get_patient_heading_corporates__corporate_id__patients__patient_id__heading_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Patient Heading
     * @description 患者頭書きを部分変更し、更新後の改訂を返す。
     */
    patch: operations["change_patient_heading_corporates__corporate_id__patients__patient_id__heading_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/names": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Patient Names
     * @description 氏名を変更する。
     */
    patch: operations["change_patient_names_corporates__corporate_id__patients__patient_id__names_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/birth-date": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Patient Birth Date
     * @description 生年月日を変更または解除する。
     */
    patch: operations["change_patient_birth_date_corporates__corporate_id__patients__patient_id__birth_date_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/profile": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Patient Profile
     * @description 性別・連絡先を部分変更して履歴へ残す。
     */
    patch: operations["change_patient_profile_corporates__corporate_id__patients__patient_id__profile_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/deactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Deactivate Patient
     * @description 患者を無効化（利用停止）する。
     */
    post: operations["deactivate_patient_corporates__corporate_id__patients__patient_id__deactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/reactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Reactivate Patient
     * @description 患者を再有効化する。
     */
    post: operations["reactivate_patient_corporates__corporate_id__patients__patient_id__reactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/merge": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Merge Patients
     * @description 患者を別の患者集約へ名寄せ統合する。
     */
    post: operations["merge_patients_corporates__corporate_id__patients__patient_id__merge_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/external-identifiers": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List External Identifiers
     * @description 患者に紐付いた外部患者IDを一覧する。
     */
    get: operations["list_external_identifiers_corporates__corporate_id__patients__patient_id__external_identifiers_get"];
    put?: never;
    /**
     * Register External Identifier
     * @description 外部システムの患者IDを紐付ける。
     */
    post: operations["register_external_identifier_corporates__corporate_id__patients__patient_id__external_identifiers_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patient-external-identifiers/{identifier_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get External Identifier
     * @description 外部患者IDを1件取得する。
     */
    get: operations["get_external_identifier_corporates__corporate_id__patient_external_identifiers__identifier_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patient-external-identifiers/{identifier_id}/deactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Deactivate External Identifier
     * @description 外部患者IDを無効化する。
     *
     *     無効化した外部IDは他の患者へ付け替えられる。誤った紐付けを直すための操作で
     *     あり、その外部IDを恒久的に使えなくするものではない。
     */
    post: operations["deactivate_external_identifier_corporates__corporate_id__patient_external_identifiers__identifier_id__deactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/coverages": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Coverages
     * @description 患者の資格を一覧する。
     */
    get: operations["list_coverages_corporates__corporate_id__patients__patient_id__coverages_get"];
    put?: never;
    /**
     * Register Coverage
     * @description 患者の資格を登録する。
     */
    post: operations["register_coverage_corporates__corporate_id__patients__patient_id__coverages_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/coverages/{coverage_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Coverage
     * @description 資格を1件取得する。
     */
    get: operations["get_coverage_corporates__corporate_id__coverages__coverage_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/coverages/{coverage_id}/period": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Change Coverage Period
     * @description 資格の有効期間を変更する。
     */
    patch: operations["change_coverage_period_corporates__corporate_id__coverages__coverage_id__period_patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/coverages/{coverage_id}/deactivation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Deactivate Coverage
     * @description 資格を無効化する。同じ発効日の再無効化だけを冪等として許す。
     */
    post: operations["deactivate_coverage_corporates__corporate_id__coverages__coverage_id__deactivation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/coverage-selections": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Record Coverage Selection
     * @description 受付で選んだ資格の組み合わせを履歴として残す。
     */
    post: operations["record_coverage_selection_corporates__corporate_id__coverage_selections_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/coverage-selections/latest": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Last Coverage Selection
     * @description 同一法人・店舗・患者の直近の選択を候補として返す。
     *
     *     履歴が無ければ ``null`` を返す。``is_still_valid`` が偽の候補をそのまま
     *     適用してはならない（適用日時点で資格が切れている）。
     */
    get: operations["get_last_coverage_selection_corporates__corporate_id__coverage_selections_latest_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/receptions/{reception_id}/medication-history": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Associate Reception Medication History
     * @description 薬剤師が選んだ薬歴を受付へ関連付ける。
     */
    post: operations["associate_reception_medication_history_corporates__corporate_id__receptions__reception_id__medication_history_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Register Prescription
     * @description 処方箋を登録する。
     *
     *     麻薬区分などを医薬品マスタから判定できない場合は失敗する。判定できないことを
     *     「該当しない」に倒すと、麻薬処方箋の必須項目チェックが素通りする。
     */
    post: operations["register_prescription_corporates__corporate_id__prescriptions_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/{prescription_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Prescription
     * @description 処方箋を1件取得する。
     */
    get: operations["get_prescription_corporates__corporate_id__prescriptions__prescription_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/{prescription_id}/readiness": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Ready For Dispensing
     * @description 調剤可能な状態にする。未回答の疑義照会が残っていれば拒否される。
     */
    post: operations["ready_for_dispensing_corporates__corporate_id__prescriptions__prescription_id__readiness_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/{prescription_id}/cancellation": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Cancel Prescription
     * @description 処方箋を取消する。
     */
    post: operations["cancel_prescription_corporates__corporate_id__prescriptions__prescription_id__cancellation_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/{prescription_id}/inquiries": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Start Inquiry
     * @description 疑義照会を開始する。
     */
    post: operations["start_inquiry_corporates__corporate_id__prescriptions__prescription_id__inquiries_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/{prescription_id}/inquiries/{inquiry_number}/resolution": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Resolve Inquiry
     * @description 疑義照会に回答する。
     */
    post: operations["resolve_inquiry_corporates__corporate_id__prescriptions__prescription_id__inquiries__inquiry_number__resolution_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/audit-interactions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Audit Drug Interactions
     * @description 処方薬・併用薬の全組み合わせの相互作用（飲み合わせ）を鑑査する。
     */
    post: operations["audit_drug_interactions_corporates__corporate_id__prescriptions_audit_interactions_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/dispensings": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Start Dispensing
     * @description 調剤を開始する。処方箋が調剤可能な状態でなければ拒否される。
     */
    post: operations["start_dispensing_corporates__corporate_id__dispensings_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/dispensings/{dispensing_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Dispensing
     * @description 調剤を1件取得する。
     */
    get: operations["get_dispensing_corporates__corporate_id__dispensings__dispensing_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/dispensings/{dispensing_id}/dispensed-content": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Record Dispensed Content
     * @description 調剤内容を記録する。
     *
     *     PUT なのは、送られた内容で調剤内容一式を置き換えるからである。差分を足す
     *     操作にすると、代替調剤の取り消しを表現できない。
     */
    put: operations["record_dispensed_content_corporates__corporate_id__dispensings__dispensing_id__dispensed_content_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/dispensings/{dispensing_id}/verification": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Verify Dispensing
     * @description 鑑査の結果を記録する。
     */
    post: operations["verify_dispensing_corporates__corporate_id__dispensings__dispensing_id__verification_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/dispensings/{dispensing_id}/audit": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Record Audit
     * @description 監査の結果を記録する。
     */
    post: operations["record_audit_corporates__corporate_id__dispensings__dispensing_id__audit_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/dispensings/{dispensing_id}/completion": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Complete Dispensing
     * @description 調剤を完了する。処方箋の状態更新と同じトランザクションで確定する。
     */
    post: operations["complete_dispensing_corporates__corporate_id__dispensings__dispensing_id__completion_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/prescriptions/{prescription_id}/dispensings": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Dispensings By Prescription
     * @description 処方箋にぶら下がる調剤を回数順に一覧する。
     */
    get: operations["list_dispensings_by_prescription_corporates__corporate_id__prescriptions__prescription_id__dispensings_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Start Medication History
     * @description 既存の初回薬歴入口をEvent作成と薬歴起票へ接続する。
     */
    post: operations["start_medication_history_corporates__corporate_id__medication_histories_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/events/{event_id}/medication-history": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Start Event Medication History
     * @description 指定Eventに対する共通薬歴下書きを作成する。
     */
    post: operations["start_event_medication_history_corporates__corporate_id__events__event_id__medication_history_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Medication History
     * @description 薬歴を1件取得する。
     */
    get: operations["get_medication_history_corporates__corporate_id__medication_histories__record_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/view": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Medication History View
     * @description 薬歴本文と読取時点の患者プロフィールを返す。
     */
    get: operations["get_medication_history_view_corporates__corporate_id__medication_histories__record_id__view_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-history-external-corrections": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List External Prescription Corrections
     * @description 薬歴の外部訂正を法人・店舗・状態でページ取得する。
     */
    get: operations["list_external_prescription_corrections_corporates__corporate_id__medication_history_external_corrections_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/external-corrections/{correction_id}/reviews": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Review External Prescription Correction
     * @description 外部訂正に理由付き判断を記録し、元の確定記録は保持する。
     */
    post: operations["review_external_prescription_correction_corporates__corporate_id__medication_histories__record_id__external_corrections__correction_id__reviews_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/draft": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    /**
     * Update Medication History Draft
     * @description 下書きを更新する。確定済みの薬歴には使えない。
     */
    put: operations["update_medication_history_draft_corporates__corporate_id__medication_histories__record_id__draft_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/finalization": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Finalize Medication History
     * @description 薬歴を確定する。頭書きへの投影も同じトランザクションで確定する。
     */
    post: operations["finalize_medication_history_corporates__corporate_id__medication_histories__record_id__finalization_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/amendments": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Amend Medication History
     * @description 確定済みの薬歴を訂正する。元の記載は消えず、訂正として積まれる。
     */
    post: operations["amend_medication_history_corporates__corporate_id__medication_histories__record_id__amendments_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/corrections": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Correct Medication History Fact
     * @description 原本を保ったまま事実訂正を追記し、頭書きを再投影する。
     */
    post: operations["correct_medication_history_fact_corporates__corporate_id__medication_histories__record_id__corrections_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/follow-ups": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Add Follow Up
     * @description 旧フォローアップ入口から独立Eventと薬歴を作成する。
     */
    post: operations["add_follow_up_corporates__corporate_id__medication_histories__record_id__follow_ups_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Record Tracing Report
     * @description 確定済み薬歴に処方医へのトレーシングレポート記録を追加する。
     */
    post: operations["record_tracing_report_corporates__corporate_id__medication_histories__record_id__tracing_reports_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/tracing-reports/{report_id}/response": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Record Tracing Report Response
     * @description トレーシングレポートに対する処方医からの返答を記録する。
     */
    post: operations["record_tracing_report_response_corporates__corporate_id__medication_histories__record_id__tracing_reports__report_id__response_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-histories/{record_id}/statutory-record-sufficiency": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Verify Statutory Record
     * @description 薬歴が調剤録の記載事項を満たすかを確認する。
     *
     *     足りないものを報告するだけで、確定や交付は止めない。
     */
    get: operations["verify_statutory_record_corporates__corporate_id__medication_histories__record_id__statutory_record_sufficiency_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/medication-histories": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Medication Histories
     * @description 患者の薬歴を一覧する。
     */
    get: operations["list_medication_histories_corporates__corporate_id__patients__patient_id__medication_histories_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/medical-profile": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Medical Profile
     * @description 頭書きを取得する。継続中の併用薬は基準日で判定する。
     */
    get: operations["get_medical_profile_corporates__corporate_id__patients__patient_id__medical_profile_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/medical-profile/rebuild": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Rebuild Medical Profile
     * @description 確定済みの薬歴から頭書きを作り直す。
     */
    post: operations["rebuild_medical_profile_corporates__corporate_id__patients__patient_id__medical_profile_rebuild_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/medication-history-category-catalog": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Medication History Category Catalog
     * @description 法人の薬歴記載区分カタログを取得する。
     */
    get: operations["get_medication_history_category_catalog_corporates__corporate_id__medication_history_category_catalog_get"];
    /**
     * Update Medication History Category Catalog
     * @description 法人の薬歴記載区分カタログを更新する。
     */
    put: operations["update_medication_history_category_catalog_corporates__corporate_id__medication_history_category_catalog_put"];
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/event-definitions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Event Definitions
     * @description 標準種別と自法人の種別を返す。
     */
    get: operations["list_event_definitions_corporates__corporate_id__event_definitions_get"];
    put?: never;
    /**
     * Create Event Definition
     * @description 法人独自のイベント種別を作成する。
     */
    post: operations["create_event_definition_corporates__corporate_id__event_definitions_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/event-definitions/{event_type_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /**
     * Update Event Definition
     * @description 法人独自のイベント種別を改名または無効化する。
     */
    patch: operations["update_event_definition_corporates__corporate_id__event_definitions__event_type_id__patch"];
    trace?: never;
  };
  "/corporates/{corporate_id}/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Create Event
     * @description 許可店舗で患者対応Eventを記録する。
     */
    post: operations["create_event_corporates__corporate_id__events_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/events/{event_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Event
     * @description Eventのメタデータと関連薬歴IDを返す。
     */
    get: operations["get_event_corporates__corporate_id__events__event_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/patients/{patient_id}/events/related-candidates": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Related Event Candidates
     * @description 許可店舗で選べる同一患者の関連Event候補を返す。
     */
    get: operations["list_related_event_candidates_corporates__corporate_id__patients__patient_id__events_related_candidates_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/medicines": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Register Medicine
     * @description 医薬品マスタへ1件取り込む（ベンダーシステム管理者専用）。
     */
    post: operations["register_medicine_medicines_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/medicines/{code_type}/{code}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Effective Medicine
     * @description 指定時点で有効な医薬品を取得する。
     */
    get: operations["get_effective_medicine_medicines__code_type___code__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/medicines/import-csv": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Import Yj Catalog
     * @description YJコードリストCSVを一括インポートする（ベンダーシステム管理者専用）。
     */
    post: operations["import_yj_catalog_medicines_import_csv_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/corporates/{corporate_id}/stores/{store_id}/integrations/nsips": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Ingest Nsips
     * @description NSIPS受付データを取り込む。
     */
    post: operations["ingest_nsips_corporates__corporate_id__stores__store_id__integrations_nsips_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /**
     * AccountStatus
     * @description アクセス権変更で指定できる状態。
     * @enum {string}
     */
    "AccountStatus-Input": "active" | "suspended";
    /**
     * AccountStatus
     * @description 個人アカウントの利用状態。
     * @enum {string}
     */
    "AccountStatus-Output": "active" | "suspended";
    /**
     * AddFollowUpRequest
     * @description フォローアップ記録の追加入力。
     */
    AddFollowUpRequest: {
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /**
       * Followed Up At
       * Format: date-time
       */
      followed_up_at: string;
      /** Method */
      method: string;
      /** Counselor Id */
      counselor_id?: string | null;
      soap?: components["schemas"]["SoapInput"];
      /**
       * Additional Notes
       * @default []
       */
      additional_notes: components["schemas"]["CategorizedNoteInput"][];
      handbook_status?: components["schemas"]["HandbookStatusInput"] | null;
      residual_drug?: components["schemas"]["ResidualDrugInput"] | null;
      /** Information Sheet Provided */
      information_sheet_provided?: boolean | null;
      profile_updates?: components["schemas"]["ProfileUpdateInput"] | null;
    };
    /**
     * AdverseReactionDto
     * @description 副作用歴の出力DTO。
     */
    AdverseReactionDto: {
      /** Medicine Name */
      medicine_name: string;
      /** Symptom */
      symptom: string;
      /** Occurred On */
      occurred_on: string | null;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * AdverseReactionIntentInput
     * @description 聞き取った副作用歴の入力。
     */
    AdverseReactionIntentInput: {
      /** Medicine Name */
      medicine_name: string;
      /** Symptom */
      symptom: string;
      /** Occurred On */
      occurred_on?: string | null;
    };
    /**
     * AllergyDto
     * @description アレルギー歴の出力DTO。
     */
    AllergyDto: {
      /** Allergen */
      allergen: string;
      /** Reaction */
      reaction: string;
      /** Severity */
      severity: string;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * AllergyIntentInput
     * @description 聞き取ったアレルギー歴の入力。
     */
    AllergyIntentInput: {
      /** Allergen */
      allergen: string;
      /** Reaction */
      reaction: string;
      /** Severity */
      severity: string;
    };
    /**
     * AmendMedicationHistoryRequest
     * @description 確定済み薬歴の訂正の入力。元の記載は残り、訂正が積まれる。
     */
    AmendMedicationHistoryRequest: {
      /** Reason */
      reason: string;
      amended_soap: components["schemas"]["SoapInput"];
    };
    /**
     * AmendmentDto
     * @description 確定済薬歴への追記の出力DTO。
     */
    AmendmentDto: {
      amended_soap: components["schemas"]["SoapDto"];
      /** Reason */
      reason: string;
      /** Amended By */
      amended_by: string;
      /** Amended At */
      amended_at: string;
      /** Amendment Id */
      amendment_id?: string | null;
    };
    /**
     * AssignConcurrentStoreRequest
     * @description 兼務の追加の入力。
     */
    AssignConcurrentStoreRequest: {
      /** Store Id */
      store_id: string;
      /**
       * Start Date
       * Format: date
       */
      start_date: string;
    };
    /**
     * AssociateReceptionMedicationHistoryRequest
     * @description 受付を薬歴へ関連付ける入力。
     */
    AssociateReceptionMedicationHistoryRequest: {
      /** Store Id */
      store_id: string;
      /** Medication History Id */
      medication_history_id: string;
    };
    /**
     * AssociateReceptionMedicationHistoryResponse
     * @description 受付と薬歴の関連結果。
     */
    AssociateReceptionMedicationHistoryResponse: {
      /** Reception Id */
      reception_id: string;
      /** Medication History Id */
      medication_history_id: string;
    };
    /**
     * AuditDrugInteractionsRequest
     * @description 相互作用鑑査リクエスト。
     */
    AuditDrugInteractionsRequest: {
      /** Yj Codes */
      yj_codes: string[];
    };
    /**
     * BillingAdditionDto
     * @description 算定加算1件の出力DTO。
     */
    BillingAdditionDto: {
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Points */
      points: number | null;
      /** Quantity */
      quantity: number | null;
      /** Id */
      id?: string | null;
    };
    /**
     * BillingAdditionRequest
     * @description 下書き編集で受け取る算定加算。
     */
    BillingAdditionRequest: {
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Points */
      points?: number | null;
      /** Quantity */
      quantity?: number | null;
    };
    /**
     * BulkRegisteredStaffResponse
     * @description スタッフ一括登録の応答。
     */
    BulkRegisteredStaffResponse: {
      /** Id */
      id: string;
      /** Staff Id */
      staff_id: string;
      /** Person Id */
      person_id: string;
      /** Account Id */
      account_id: string;
      /** Membership Id */
      membership_id: string;
      /** Email */
      email: string;
    };
    /**
     * BusinessDayExceptionDto
     * @description 特例日の公開値。
     */
    BusinessDayExceptionDto: {
      /**
       * On
       * Format: date
       */
      on: string;
      /** Slots */
      slots: components["schemas"]["BusinessHourSlotDto"][];
      /** Note */
      note: string | null;
    };
    /**
     * BusinessDayExceptionInput
     * @description 日付を指定した上書き。時間帯が空なら臨時休業。
     */
    BusinessDayExceptionInput: {
      /**
       * On
       * Format: date
       */
      on: string;
      /**
       * Slots
       * @default []
       */
      slots: components["schemas"]["BusinessHourSlotInput"][];
      /** Note */
      note?: string | null;
    };
    /**
     * BusinessHourSlotDto
     * @description 開局時間帯の公開値。
     */
    BusinessHourSlotDto: {
      /**
       * Opens At
       * Format: time
       */
      opens_at: string;
      /**
       * Closes At
       * Format: time
       */
      closes_at: string;
    };
    /**
     * BusinessHourSlotInput
     * @description 開局時間帯1件。終了時刻の 00:00 はその日の24時を指す。
     */
    BusinessHourSlotInput: {
      /**
       * Opens At
       * Format: time
       */
      opens_at: string;
      /**
       * Closes At
       * Format: time
       */
      closes_at: string;
    };
    /**
     * BusinessHoursDto
     * @description 開局時間の公開値。
     */
    BusinessHoursDto: {
      /** Weekly */
      weekly: components["schemas"]["WeekdayBusinessHoursDto"][];
      /** Exceptions */
      exceptions: components["schemas"]["BusinessDayExceptionDto"][];
    };
    /**
     * BusinessWeekday
     * @description 開局予定を組み立てる曜日。
     * @enum {string}
     */
    BusinessWeekday:
      | "monday"
      | "tuesday"
      | "wednesday"
      | "thursday"
      | "friday"
      | "saturday"
      | "sunday";
    /**
     * CategorizedNoteDto
     * @description 大区分・中区分に紐づく記載メモ1件の出力DTO。
     */
    CategorizedNoteDto: {
      /** Major Category Code */
      major_category_code: string;
      /** Medium Category Code */
      medium_category_code: string;
      /** Text */
      text: string;
      /** Category */
      category: string;
      /** Id */
      id?: string | null;
    };
    /**
     * CategorizedNoteInput
     * @description 大区分・中区分に紐づく記載メモ1件の入力。
     */
    CategorizedNoteInput: {
      /** Major Category Code */
      major_category_code: string;
      /** Medium Category Code */
      medium_category_code: string;
      /** Text */
      text: string;
      /**
       * Category
       * @default general
       */
      category: string;
    };
    /**
     * CategoryCatalogDto
     * @description 区分カタログ集約の出力DTO。
     */
    CategoryCatalogDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Major Categories */
      major_categories: components["schemas"]["MajorCategoryDto"][];
      /** Medium Categories */
      medium_categories: components["schemas"]["MediumCategoryDto"][];
    };
    /**
     * ChangeBusinessHoursRequest
     * @description 開局時間の一括置き換え。曜日は7つすべてを指定する。
     *
     *     入れ子はApplication層の入力DTOをそのまま型に置く。ここで写し取ると、
     *     項目が増えたときに黙って落ちる項目ができる。
     */
    ChangeBusinessHoursRequest: {
      /** Weekly */
      weekly: components["schemas"]["WeekdayBusinessHoursInput"][];
      /**
       * Exceptions
       * @default []
       */
      exceptions: components["schemas"]["BusinessDayExceptionInput"][];
    };
    /**
     * ChangeCorporateNameRequest
     * @description 法人名変更の入力。
     */
    ChangeCorporateNameRequest: {
      /** Name */
      name: string;
    };
    /**
     * ChangeCorporateStatusRequest
     * @description 法人の利用状態変更の入力。
     */
    ChangeCorporateStatusRequest: {
      /** Is Active */
      is_active: boolean;
    };
    /**
     * ChangeCoveragePeriodRequest
     * @description 資格期間変更の入力。``valid_to`` の ``None`` は無期限を意味する。
     */
    ChangeCoveragePeriodRequest: {
      /**
       * Valid From
       * Format: date
       */
      valid_from: string;
      /** Valid To */
      valid_to?: string | null;
    };
    /**
     * ChangeInsurancePharmacyNumberRequest
     * @description 保険薬局指定番号変更の入力。``None``・空文字・空白はいずれも解除を意味する。
     */
    ChangeInsurancePharmacyNumberRequest: {
      /** Insurance Pharmacy Number */
      insurance_pharmacy_number?: string | null;
    };
    /**
     * ChangeMembershipRequest
     * @description 同じ本人・アカウントの法人アクセス権の変更。
     */
    ChangeMembershipRequest: {
      status?: components["schemas"]["AccountStatus-Input"] | null;
      role?: components["schemas"]["MembershipRole-Input"] | null;
      /** Store Ids */
      store_ids?: string[] | null;
      /** Store Id */
      store_id?: string | null;
      /** Store Is Active */
      store_is_active?: boolean | null;
    };
    /**
     * ChangePasswordRequest
     * @description 変更専用セッションでも使えるパスワード変更入力。
     */
    ChangePasswordRequest: {
      /** Password */
      password: string;
    };
    /**
     * ChangePatientBirthDateRequest
     * @description 生年月日変更の入力。``None`` は解除を意味する。
     */
    ChangePatientBirthDateRequest: {
      /** Birth Date */
      birth_date?: string | null;
    };
    /**
     * ChangePatientHeadingRequest
     * @description 患者頭書きの部分変更入力。省略と明示的なnullを区別する。
     */
    ChangePatientHeadingRequest: {
      /** Expected Revision */
      expected_revision: number;
      /** Summary */
      summary?: string | null;
      /** Notes */
      notes?: string | null;
    };
    /**
     * ChangePatientNamesRequest
     * @description 氏名変更の入力。
     */
    ChangePatientNamesRequest: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
    };
    /**
     * ChangePatientProfileRequest
     * @description 連絡先・性別の部分変更入力。省略と明示的なnullを区別する。
     */
    ChangePatientProfileRequest: {
      /** Gender */
      gender?: string | null;
      /** Postal Code */
      postal_code?: string | null;
      /** Address */
      address?: string | null;
      /** Phone Number */
      phone_number?: string | null;
    };
    /**
     * ChangeRepresentativeRequest
     * @description 代表者名変更の入力。
     */
    ChangeRepresentativeRequest: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
    };
    /**
     * ChangeStaffJobTitleRequest
     * @description 役職変更の入力。``None``・空文字・空白はいずれも解除を意味する。
     */
    ChangeStaffJobTitleRequest: {
      /** Job Title */
      job_title?: string | null;
    };
    /**
     * ChangeStaffNamesRequest
     * @description 氏名変更の入力。
     */
    ChangeStaffNamesRequest: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
    };
    /**
     * ChangeStoreAddressRequest
     * @description 店舗所在地変更の入力。
     */
    ChangeStoreAddressRequest: {
      /** Postal Code */
      postal_code: string;
      /** Address */
      address: string;
    };
    /**
     * ChangeStoreCodeRequest
     * @description 店舗コード変更の入力。``None``・空文字・空白はいずれも解除を意味する。
     */
    ChangeStoreCodeRequest: {
      /** Code */
      code?: string | null;
    };
    /**
     * ChangeStoreContactInfoRequest
     * @description 店舗連絡先変更の入力。
     */
    ChangeStoreContactInfoRequest: {
      /** Phone Number */
      phone_number: string;
      /** Fax Number */
      fax_number?: string | null;
      /** Email */
      email?: string | null;
    };
    /**
     * ChangeStoreNamesRequest
     * @description 店舗名変更の入力。
     */
    ChangeStoreNamesRequest: {
      /** Name */
      name: string;
      /** Name Kana */
      name_kana: string;
      /** Name Romaji */
      name_romaji?: string | null;
    };
    /**
     * ChangeStoreStatusRequest
     * @description 状態変更理由。操作者・日時は入力しない。
     */
    ChangeStoreStatusRequest: {
      /** Reason */
      reason: string;
    };
    /**
     * CompleteDispensingRequest
     * @description 調剤完了の入力。分割調剤では次回予定日を伴う。
     */
    CompleteDispensingRequest: {
      /** Completion Type */
      completion_type: string;
      /** Next Dispensing Date */
      next_dispensing_date?: string | null;
    };
    /**
     * ConcurrentMedicationDto
     * @description 併用薬の出力DTO。
     *
     *     ``is_active`` は返さない。継続中かどうかは適用日ごとに決まるので、
     *     DTOへ焼き付けると受け取り側が古い判定を持ち回ることになる。
     */
    ConcurrentMedicationDto: {
      /** Medicine Name */
      medicine_name: string;
      /** Category */
      category: string;
      /** Started On */
      started_on: string;
      /** Ended On */
      ended_on: string | null;
      /** Prescriber Institution */
      prescriber_institution: string | null;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * ConcurrentMedicationIntentInput
     * @description 聞き取った併用薬の開始の入力。
     */
    ConcurrentMedicationIntentInput: {
      /** Medicine Name */
      medicine_name: string;
      /** Category */
      category: string;
      /**
       * Started On
       * Format: date
       */
      started_on: string;
      /** Prescriber Institution */
      prescriber_institution?: string | null;
    };
    /**
     * ConditionIntentInput
     * @description 聞き取った疾患の入力。
     */
    ConditionIntentInput: {
      /** Condition Name */
      condition_name: string;
      /** Condition Status */
      condition_status: string;
      /**
       * Is Contraindication Target
       * @default false
       */
      is_contraindication_target: boolean;
    };
    /**
     * CorporatePageDto
     * @description 法人一覧の一ページ。
     */
    CorporatePageDto: {
      /** Items */
      items: components["schemas"]["CorporateResponseDto"][];
      /** Next Cursor */
      next_cursor: string | null;
    };
    /**
     * CorporatePolicyDto
     * @description 法人ポリシーの出力データ。
     */
    CorporatePolicyDto: {
      require_prescription_audit: components["schemas"]["PolicySettingDto"];
      prohibit_self_verification: components["schemas"]["PolicySettingDto"];
    };
    /**
     * CorporateResponseDto
     * @description 取得結果として画面やAPIに返すデータ構造（DTO）
     */
    CorporateResponseDto: {
      /** Id */
      id: string;
      /** Name */
      name: string;
      /** Representative Name */
      representative_name: string;
      /** Is Active */
      is_active: boolean;
      policy: components["schemas"]["CorporatePolicyDto"];
    };
    /**
     * CorrectMedicationHistoryFactRequest
     * @description 確定済み薬歴の事実訂正。訂正者と時刻はサーバ側で決める。
     */
    CorrectMedicationHistoryFactRequest: {
      /** Target */
      target: string;
      /**
       * Operation
       * @default replace
       * @enum {string}
       */
      operation: "replace" | "retract" | "append";
      /** Reason */
      reason: string;
      /** Value */
      value?: unknown | null;
    };
    /**
     * CoverageSelectionDto
     * @description 受付で固定した保険・公費の選択の出力DTO。
     *
     *     ドメイン側と同じ枠構造で返す。平坦な元ID列を併記すると、消費側が位置で
     *     値と対応づける余地が戻ってしまうため持たせない。
     */
    CoverageSelectionDto: {
      insurance: components["schemas"]["InsuranceCoverageSelectionDto"] | null;
      /** Public Expenses */
      public_expenses: components["schemas"]["PublicExpenseCoverageSelectionDto"][];
    };
    /**
     * CoverageSelectionRecordDto
     * @description 適用資格選択履歴の出力DTO。
     */
    CoverageSelectionRecordDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Applied On */
      applied_on: string;
      selection: components["schemas"]["CoverageSelectionDto"];
      /** Recorded At */
      recorded_at: string;
      /** Recorded By */
      recorded_by: string;
    };
    /**
     * CreateEventDefinitionRequest
     * @description 法人独自イベント種別の作成入力。
     */
    CreateEventDefinitionRequest: {
      /** Name */
      name: string;
    };
    /**
     * CreateEventRequest
     * @description 新しい患者対応Eventの入力。
     */
    CreateEventRequest: {
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Event Type Id */
      event_type_id: string;
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
      /** Related Event Id */
      related_event_id?: string | null;
      /** Reception Id */
      reception_id?: string | null;
      /** Prescription Id */
      prescription_id?: string | null;
      /** Dispensing Id */
      dispensing_id?: string | null;
    };
    /**
     * CurrentActorDto
     * @description いま操作している本人・アカウント・権限の範囲。
     */
    CurrentActorDto: {
      /** Person Id */
      person_id: string | null;
      /** Account Id */
      account_id: string | null;
      /** Membership Id */
      membership_id: string | null;
      /** Corporate Id */
      corporate_id: string | null;
      /** Roles */
      roles: string[];
      /** Staff Id */
      staff_id: string | null;
      /** Store Ids */
      store_ids: string[];
      /** Managed Store Ids */
      managed_store_ids: string[];
      /** Permissions */
      permissions: components["schemas"]["UserPermissionDto"][];
      /** Selected Store Id */
      selected_store_id?: string | null;
    };
    /**
     * DeactivateCoverageRequest
     * @description 資格無効化の入力。発効日当日は既に無効として扱う。
     */
    DeactivateCoverageRequest: {
      /**
       * Effective On
       * Format: date
       */
      effective_on: string;
    };
    /**
     * DeactivatePatientRequest
     * @description 患者無効化の入力。
     */
    DeactivatePatientRequest: {
      /** Reason */
      reason: string;
    };
    /**
     * DepartmentDto
     * @description 診療科の出力DTO。
     */
    DepartmentDto: {
      /** Code Type */
      code_type: string;
      /** Name */
      name: string | null;
      /** Code */
      code: string | null;
    };
    /**
     * DepartmentInput
     * @description 診療科の入力（JAHIS レコードNo.4）。
     */
    DepartmentInput: {
      /** Code Type */
      code_type: string;
      /** Name */
      name: string | null;
      /** Code */
      code?: string | null;
    };
    /**
     * DispensedMedicineDto
     * @description 調剤した薬品1明細の出力DTO。
     */
    DispensedMedicineDto: {
      /** Line Number */
      line_number: number;
      /** Code Type */
      code_type: string;
      /** Code */
      code: string | null;
      /** Name */
      name: string;
      /** Amount */
      amount: string;
      /** Unit */
      unit: string;
      substitution: components["schemas"]["SubstitutionDto"] | null;
      /** Preparations */
      preparations: string[];
      /** Public Expense First */
      public_expense_first: boolean;
      /** Public Expense Second */
      public_expense_second: boolean;
      /** Public Expense Third */
      public_expense_third: boolean;
      /** Public Expense Special */
      public_expense_special: boolean;
    };
    /**
     * DispensedMedicineInput
     * @description 調剤した薬品1明細の入力。
     */
    DispensedMedicineInput: {
      /** Line Number */
      line_number: number;
      /** Code Type */
      code_type: string;
      /** Name */
      name: string;
      /** Amount */
      amount: string;
      /** Unit */
      unit: string;
      /** Code */
      code?: string | null;
      substitution?: components["schemas"]["SubstitutionInput"] | null;
      /** Preparations */
      preparations?: string[];
      /**
       * Public Expense First
       * @default false
       */
      public_expense_first: boolean;
      /**
       * Public Expense Second
       * @default false
       */
      public_expense_second: boolean;
      /**
       * Public Expense Third
       * @default false
       */
      public_expense_third: boolean;
      /**
       * Public Expense Special
       * @default false
       */
      public_expense_special: boolean;
    };
    /**
     * DispensedRpDto
     * @description 調剤した剤（Rp）の出力DTO。
     */
    DispensedRpDto: {
      /** Rp Number */
      rp_number: number;
      /** Category */
      category: string;
      /** Quantity */
      quantity: number;
      dosage_instruction: components["schemas"]["DosageInstructionDto"];
      /** Medicines */
      medicines: components["schemas"]["DispensedMedicineDto"][];
      quantity_adjustment:
        components["schemas"]["QuantityAdjustmentDto"] | null;
    };
    /**
     * DispensedRpInput
     * @description 調剤した剤（Rp）の入力。
     */
    DispensedRpInput: {
      /** Rp Number */
      rp_number: number;
      /** Category */
      category: string;
      /** Quantity */
      quantity: number;
      /** Dosage Code Type */
      dosage_code_type: string;
      /** Dosage Name */
      dosage_name: string;
      /** Medicines */
      medicines: components["schemas"]["DispensedMedicineInput"][];
      /** Dosage Code */
      dosage_code?: string | null;
      /** Daily Frequency */
      daily_frequency?: number | null;
      quantity_adjustment?:
        components["schemas"]["QuantityAdjustmentInput"] | null;
    };
    /**
     * DispensingAuditDto
     * @description 処方鑑査の出力DTO。
     */
    DispensingAuditDto: {
      /** Auditor Id */
      auditor_id: string;
      /** Audited At */
      audited_at: string;
      /** Has Issues */
      has_issues: boolean;
      /** Notes */
      notes: string | null;
    };
    /**
     * DispensingProcessDto
     * @description 調剤セッションの出力DTO。
     */
    DispensingProcessDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Prescription Id */
      prescription_id: string;
      /** Iteration */
      iteration: number;
      /** Dispensed Date */
      dispensed_date: string;
      /** Dispenser Id */
      dispenser_id: string;
      /** Started At */
      started_at: string;
      /** Status */
      status: string;
      /** Completion Type */
      completion_type: string;
      /** Split Reason */
      split_reason: string | null;
      /** Total Split Count */
      total_split_count?: number | null;
      /** Next Dispensing Date */
      next_dispensing_date: string | null;
      /** Dispensed Rps */
      dispensed_rps: components["schemas"]["DispensedRpDto"][];
      audit: components["schemas"]["DispensingAuditDto"] | null;
      verification: components["schemas"]["DispensingVerificationDto"] | null;
      /** Cancellation Reason */
      cancellation_reason: string | null;
    };
    /**
     * DispensingVerificationDto
     * @description 最終鑑査の出力DTO。
     */
    DispensingVerificationDto: {
      /** Verifier Id */
      verifier_id: string;
      /** Verified At */
      verified_at: string;
      /** Result */
      result: string;
      /** Notes */
      notes: string | null;
    };
    /**
     * DosageInstructionDto
     * @description 用法の出力DTO。
     */
    DosageInstructionDto: {
      /** Code Type */
      code_type: string;
      /** Name */
      name: string;
      /** Code */
      code: string | null;
      /** Daily Frequency */
      daily_frequency: number | null;
    };
    /**
     * DosageInstructionInput
     * @description 用法の入力（JAHIS レコードNo.111）。
     */
    DosageInstructionInput: {
      /** Code Type */
      code_type: string;
      /** Name */
      name: string;
      /** Code */
      code?: string | null;
      /** Daily Frequency */
      daily_frequency?: number | null;
    };
    /**
     * DosageSupplementDto
     * @description 用法補足の出力DTO。
     */
    DosageSupplementDto: {
      /** Supplement Type */
      supplement_type: string;
      /** Text */
      text: string;
      /** Code */
      code: string | null;
      /** Site Code */
      site_code: string | null;
    };
    /**
     * DosageSupplementInput
     * @description 用法補足の入力（JAHIS レコードNo.181 / 処方編 別表14）。
     */
    DosageSupplementInput: {
      /** Supplement Type */
      supplement_type: string;
      /** Text */
      text: string;
      /** Code */
      code?: string | null;
      /** Site Code */
      site_code?: string | null;
    };
    /**
     * DrugInteractionAuditReportDto
     * @description 相互作用鑑査レポートDTO。
     */
    DrugInteractionAuditReportDto: {
      /** Target Yj Codes */
      target_yj_codes: string[];
      /** Total Combinations */
      total_combinations: number;
      /** Contraindicated Count */
      contraindicated_count: number;
      /** Precaution Count */
      precaution_count: number;
      /** Has Contraindications */
      has_contraindications: boolean;
      /** Has Precautions */
      has_precautions: boolean;
      /** Pairs */
      pairs: components["schemas"]["DrugInteractionPairDto"][];
    };
    /**
     * DrugInteractionPairDto
     * @description 飲み合わせ判定結果DTO。
     */
    DrugInteractionPairDto: {
      /** Medicine A */
      medicine_a: string;
      /** Medicine B */
      medicine_b: string;
      /** Severity */
      severity: string;
      /** Severity Label */
      severity_label: string;
      /** Clinical Condition */
      clinical_condition: string;
      /** Mechanism */
      mechanism: string;
      /** Recommendation */
      recommendation: string;
    };
    /**
     * EffectivePolicyDto
     * @description 店舗の実効ポリシー投影。
     */
    EffectivePolicyDto: {
      require_prescription_audit: components["schemas"]["EffectivePolicyItemDto"];
      prohibit_self_verification: components["schemas"]["EffectivePolicyItemDto"];
    };
    /**
     * EffectivePolicyItemDto
     * @description 単一ポリシー項目の実効値と解決元。
     */
    EffectivePolicyItemDto: {
      /** Value */
      value: boolean;
      /**
       * Source
       * @enum {string}
       */
      source: "corporate" | "store";
    };
    /**
     * EndManagerRequest
     * @description 任命の終了日。
     */
    EndManagerRequest: {
      /**
       * Ends On
       * Format: date
       */
      ends_on: string;
    };
    /**
     * ErrorResponse
     * @description すべての失敗応答が共有する本文。
     *
     *     成功以外はこの形1つに揃える。``code`` は安定した識別子でクライアントの分岐に
     *     使い、``message`` は人が読むためのもので分岐に使わせない。``errors`` は入力
     *     検証のときだけ埋まるが、キー自体は常に存在させる（有無で形が変わると、結局
     *     2種類の本文を扱うことになる）。
     */
    ErrorResponse: {
      /** Code */
      code: string;
      /** Message */
      message: string;
      /**
       * Errors
       * @default []
       */
      errors: components["schemas"]["FieldError"][];
    };
    /**
     * EventDefinitionDto
     * @description イベント種別の外向けDTO。
     */
    EventDefinitionDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string | null;
      /** Name */
      name: string;
      /** Standard Code */
      standard_code: string | null;
      /** Is Active */
      is_active: boolean;
    };
    /**
     * EventDto
     * @description Eventと薬歴の有無を返すDTO。
     */
    EventDto: {
      /** Event Id */
      event_id: string;
      /** Medication History Id */
      medication_history_id: string | null;
      /** Event Type Id */
      event_type_id: string;
      /** Event Type Name */
      event_type_name: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Occurred At */
      occurred_at: string | null;
      /** Occurred At Is Unknown */
      occurred_at_is_unknown: boolean;
      /** Created At */
      created_at: string;
      /** Related Event Id */
      related_event_id: string | null;
      /** Reception Id */
      reception_id: string | null;
      /** Prescription Id */
      prescription_id: string | null;
      /** Dispensing Id */
      dispensing_id: string | null;
    };
    /**
     * ExternalCorrectionReviewEventDto
     * @description 外部訂正への判断イベントDTO。
     */
    ExternalCorrectionReviewEventDto: {
      /** Decision */
      decision: string;
      /** Reason */
      reason: string;
      /** Reviewed By */
      reviewed_by: string;
      /** Reviewed At */
      reviewed_at: string;
      /** Matched Prescription Id */
      matched_prescription_id: string | null;
      /** Amendment Id */
      amendment_id?: string | null;
    };
    /**
     * ExternalPrescriptionCorrectionDto
     * @description 外部処方訂正の受信事実と判断履歴DTO。
     */
    ExternalPrescriptionCorrectionDto: {
      /** Correction Id */
      correction_id: string;
      /** Kind */
      kind: string;
      /** Status */
      status: string;
      /** Corrected At */
      corrected_at: string;
      /** Source Document Number */
      source_document_number: string;
      /** Reason */
      reason: string;
      /** Details */
      details: string | null;
      /** Acknowledged By */
      acknowledged_by: string | null;
      /** Acknowledged At */
      acknowledged_at: string | null;
      /** Review Events */
      review_events: components["schemas"]["ExternalCorrectionReviewEventDto"][];
    };
    /**
     * FamilyPharmacistDto
     * @description かかりつけ薬剤師の出力DTO。
     */
    FamilyPharmacistDto: {
      /** Pharmacist Id */
      pharmacist_id: string;
      /** Agreed On */
      agreed_on: string;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * FieldError
     * @description 入力検証で弾かれた項目1件。
     */
    FieldError: {
      /** Location */
      location: string;
      /** Message */
      message: string;
    };
    /**
     * FinalizeMedicationHistoryRequest
     * @description 薬歴確定の入力。
     */
    FinalizeMedicationHistoryRequest: {
      /** Counseled At */
      counseled_at?: string | null;
      /** Event Occurred At */
      event_occurred_at?: string | null;
      /** Delay Reason */
      delay_reason?: string | null;
      /** Review Result */
      review_result?: string | null;
    };
    /**
     * GenericPreferenceDto
     * @description 後発医薬品への意向の出力DTO。
     */
    GenericPreferenceDto: {
      /** Preference */
      preference: string;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * HandbookStatusDto
     * @description お薬手帳の活用状況の出力DTO。
     */
    HandbookStatusDto: {
      /** Presented */
      presented: boolean;
      /** Not Presented Reason */
      not_presented_reason: string | null;
      /** Guidance Provided */
      guidance_provided: boolean | null;
      /** Multiple Handbooks Not Consolidated Reason */
      multiple_handbooks_not_consolidated_reason: string | null;
    };
    /**
     * HandbookStatusInput
     * @description お薬手帳の活用状況の入力（法定記載事項ウ（ト））。
     */
    HandbookStatusInput: {
      /** Presented */
      presented: boolean;
      /** Not Presented Reason */
      not_presented_reason?: string | null;
      /** Guidance Provided */
      guidance_provided?: boolean | null;
      /** Multiple Handbooks Not Consolidated Reason */
      multiple_handbooks_not_consolidated_reason?: string | null;
    };
    /**
     * ImportYjCatalogRequest
     * @description YJコードリストCSVインポートの入力。
     */
    ImportYjCatalogRequest: {
      /** Csv Text */
      csv_text?: string | null;
      /** Catalog Version */
      catalog_version?: string | null;
    };
    /**
     * ImportYjCatalogResultDto
     * @description インポート実行結果DTO。
     */
    ImportYjCatalogResultDto: {
      /** Total Rows */
      total_rows: number;
      /** Imported Count */
      imported_count: number;
      /** Skipped Count */
      skipped_count: number;
      /**
       * Catalog Version
       * Format: date
       */
      catalog_version: string;
    };
    /**
     * IngestNsipsRequest
     * @description NSIPS取込リクエストボディ。
     */
    IngestNsipsRequest: {
      /** Dispenser Staff Id */
      dispenser_staff_id: string;
      /** Reception Id */
      reception_id: string;
      /** Raw Nsips Text */
      raw_nsips_text?: string | null;
      structured_bundle?: components["schemas"]["NsipsBundleRequest"] | null;
    };
    /**
     * IngestNsipsResultDto
     * @description NSIPS取込結果DTO。
     *
     *     保険情報の不足は情報として返す。請求用資格を自動選択しないため、
     *     coverage_selection_record_id は未設定で返す。
     */
    IngestNsipsResultDto: {
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Prescription Id */
      prescription_id?: string | null;
      /** Dispensing Id */
      dispensing_id?: string | null;
      /** Medication History Id */
      medication_history_id?: string | null;
      /** Follow Up Id */
      follow_up_id?: string | null;
      /** Document Number */
      document_number?: string | null;
      /** Patient Name */
      patient_name: string;
      /** Is New Patient */
      is_new_patient: boolean;
      /**
       * Is Duplicate
       * @default false
       */
      is_duplicate: boolean;
      /**
       * Is Follow Up Only
       * @default false
       */
      is_follow_up_only: boolean;
      /**
       * Has Pending Correction Review
       * @default false
       */
      has_pending_correction_review: boolean;
      /**
       * Patient Attribute Conflicts
       * @default []
       */
      patient_attribute_conflicts: string[];
      /**
       * Patient Profile Updated Fields
       * @default []
       */
      patient_profile_updated_fields: string[];
      /**
       * Coverage Review Required
       * @default false
       */
      coverage_review_required: boolean;
      /** Coverage Review Reason */
      coverage_review_reason?: string | null;
      /** Coverage Selection Record Id */
      coverage_selection_record_id?: string | null;
      /** Dispensed Date */
      dispensed_date?: string | null;
      /**
       * Addition Names
       * @default []
       */
      addition_names: string[];
    };
    /**
     * InsuranceCoverageSelectionDto
     * @description 医療保険枠の出力DTO。選択元IDと請求固定値を束ねたまま返す。
     */
    InsuranceCoverageSelectionDto: {
      /** Source Coverage Id */
      source_coverage_id: string;
      /** Insurer Number */
      insurer_number: string;
      /** Insured Symbol */
      insured_symbol: string;
      /** Insured Number */
      insured_number: string;
      /** Insured Type */
      insured_type: string;
      /** Branch Number */
      branch_number: string | null;
      /** Benefit Ratio */
      benefit_ratio: number;
    };
    /**
     * LabeledNoteDto
     * @description ラベル付き記述1件の出力DTO。
     */
    LabeledNoteDto: {
      /** Category */
      category: string;
      /** Category Label */
      category_label: string;
      /** Text */
      text: string;
    };
    /**
     * LabeledNoteInput
     * @description 法定カテゴリを付けた自由記述1件の入力。
     */
    LabeledNoteInput: {
      /** Text */
      text: string;
      /**
       * Category
       * @default general
       */
      category: string;
    };
    /**
     * LastCoverageSelectionCandidateDto
     * @description 最新履歴と今回の適用日における真正性。
     */
    LastCoverageSelectionCandidateDto: {
      record: components["schemas"]["CoverageSelectionRecordDto"];
      /** Is Still Valid */
      is_still_valid: boolean;
    };
    /**
     * LifestyleDto
     * @description 生活像の出力DTO。
     */
    LifestyleDto: {
      /** Note */
      note: string;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * LinkPersonRequest
     * @description 既存本人との明示的な対応。氏名推測はしない。
     */
    LinkPersonRequest: {
      /** Person Id */
      person_id: string;
    };
    /**
     * LoginRequest
     * @description ログイン入力。秘密をモデルの文字列表現へ含めない。
     */
    LoginRequest: {
      /** Corporate Id */
      corporate_id: string;
      /** Email */
      email: string;
      /** Password */
      password: string;
    };
    /**
     * LoginSession
     * @description 秘密は応答時だけ渡し、通常の文字列表現には含めない。
     */
    LoginSession: {
      /** Access Token */
      access_token: string;
      /** Password Change Required */
      password_change_required: boolean;
      /** Selected Store Id */
      selected_store_id?: string | null;
    };
    /**
     * MajorCategoryDto
     * @description 大区分の出力DTO。
     */
    MajorCategoryDto: {
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Display Order */
      display_order: number;
      /** Is Enabled */
      is_enabled: boolean;
    };
    /**
     * MajorCategoryInput
     * @description 大区分定義の入力。
     */
    MajorCategoryInput: {
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Display Order */
      display_order: number;
      /**
       * Is Enabled
       * @default true
       */
      is_enabled: boolean;
    };
    /**
     * ManageManagerRequest
     * @description 管理薬剤師の任命履歴への操作。
     */
    ManageManagerRequest: {
      /** @default appoint */
      action: components["schemas"]["ManagerAction"];
      /** Assignment Id */
      assignment_id?: string | null;
      /** Staff Id */
      staff_id?: string | null;
      /** Starts On */
      starts_on?: string | null;
      /** Ends On */
      ends_on?: string | null;
    };
    /**
     * ManagerAction
     * @description 任命履歴への更新分類。
     * @enum {string}
     */
    ManagerAction: "appoint" | "replace" | "cancel" | "end";
    /**
     * ManagerAssignmentDto
     * @description 任命履歴の公開値。
     */
    ManagerAssignmentDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Staff Id */
      staff_id: string;
      /**
       * Starts On
       * Format: date
       */
      starts_on: string;
      /** Ends On */
      ends_on: string | null;
      /** Status */
      status: string;
    };
    /**
     * MedicalConditionDto
     * @description 疾患の出力DTO。
     */
    MedicalConditionDto: {
      /** Condition Name */
      condition_name: string;
      /** Condition Status */
      condition_status: string;
      /** Is Contraindication Target */
      is_contraindication_target: boolean;
      provenance: components["schemas"]["ProvenanceDto"];
    };
    /**
     * MedicalInstitutionDto
     * @description 保険医療機関の出力DTO。
     */
    MedicalInstitutionDto: {
      /** Code Type */
      code_type: string;
      /** Code */
      code: string;
      /** Prefecture Code */
      prefecture_code: string | null;
      /** Name */
      name: string;
      /** Postal Code */
      postal_code: string | null;
      /** Address */
      address: string | null;
      /** Phone Number */
      phone_number: string | null;
      /** Fax Number */
      fax_number: string | null;
    };
    /**
     * MedicalInstitutionInput
     * @description 保険医療機関の入力（JAHIS レコードNo.1 / No.2）。
     */
    MedicalInstitutionInput: {
      /** Code Type */
      code_type: string;
      /** Code */
      code: string;
      /** Prefecture Code */
      prefecture_code: string | null;
      /** Name */
      name: string;
      /** Postal Code */
      postal_code?: string | null;
      /** Address */
      address?: string | null;
      /** Phone Number */
      phone_number?: string | null;
      /** Fax Number */
      fax_number?: string | null;
    };
    /**
     * MedicationHistoryDto
     * @description 薬歴取得ユースケースの出力DTO。
     */
    MedicationHistoryDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Event Id */
      event_id: string;
      /** Event Type Id */
      event_type_id: string | null;
      /** Event Type Name */
      event_type_name: string | null;
      /** Event Occurred At */
      event_occurred_at: string | null;
      /** Event Occurred At Is Unknown */
      event_occurred_at_is_unknown: boolean;
      /** Dispensing Id */
      dispensing_id: string | null;
      /** Prescription Id */
      prescription_id: string | null;
      /** Counselor Id */
      counselor_id: string | null;
      /** Counseled At */
      counseled_at: string | null;
      /** Method */
      method: string | null;
      /** Status */
      status: string;
      soap: components["schemas"]["SoapDto"];
      effective_soap: components["schemas"]["SoapDto"];
      handbook_status: components["schemas"]["HandbookStatusDto"] | null;
      residual_drug: components["schemas"]["ResidualDrugDto"] | null;
      /** Information Sheet Provided */
      information_sheet_provided: boolean | null;
      /** Source System */
      source_system: string | null;
      /** Imported At */
      imported_at: string | null;
      /** Amendments */
      amendments: components["schemas"]["AmendmentDto"][];
      /** External Corrections */
      external_corrections: components["schemas"]["ExternalPrescriptionCorrectionDto"][];
      /** Updates Profile */
      updates_profile: boolean;
      /** Profile Updates */
      profile_updates: {
        [key: string]: unknown;
      };
      /** Original Facts */
      original_facts: {
        [key: string]: unknown;
      };
      /** Fact Corrections */
      fact_corrections: {
        [key: string]: unknown;
      }[];
      /**
       * Additional Notes
       * @default []
       */
      additional_notes: components["schemas"]["CategorizedNoteDto"][];
      /**
       * Billing Additions
       * @default []
       */
      billing_additions: components["schemas"]["BillingAdditionDto"][];
      /**
       * Tracing Reports
       * @default []
       */
      tracing_reports: components["schemas"]["TracingReportDto"][];
      /** Finalized At */
      finalized_at?: string | null;
      /** Finalized By */
      finalized_by?: string | null;
      /** Delay Reason */
      delay_reason?: string | null;
      /** Recorded By */
      recorded_by?: string | null;
      /** Review Result */
      review_result?: string | null;
      /** Recorded At */
      recorded_at?: string | null;
    };
    /**
     * MedicationHistoryPatientProfileDto
     * @description 薬歴表示時に参照する患者の現行プロフィール。
     */
    MedicationHistoryPatientProfileDto: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      /** Birth Date */
      birth_date: string | null;
      /** Gender */
      gender: string | null;
      /** Postal Code */
      postal_code: string | null;
      /** Address */
      address: string | null;
      /** Phone Number */
      phone_number: string | null;
    };
    /**
     * MedicationHistoryViewDto
     * @description 確定薬歴と読取時点の患者プロフィール。
     */
    MedicationHistoryViewDto: {
      record: components["schemas"]["MedicationHistoryDto"];
      current_patient_profile: components["schemas"]["MedicationHistoryPatientProfileDto"];
    };
    /**
     * MedicineDto
     * @description 医薬品マスタ1行の出力DTO。
     *
     *     導出値（``is_narcotic`` 等）も返す。呼び出し側が生の事実から判定し直すと、
     *     規則の実装が2箇所に分かれる。
     */
    MedicineDto: {
      /** Id */
      id: string;
      /** Code Type */
      code_type: string;
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Unit */
      unit: string;
      /** Dosage Form */
      dosage_form: string;
      /** Listed On */
      listed_on: string;
      /** Withdrawn On */
      withdrawn_on: string | null;
      /** Catalog Version */
      catalog_version: string;
      /** Narcotic Category */
      narcotic_category: string;
      /** Generic Category */
      generic_category: string;
      /** Has Dosage Limit */
      has_dosage_limit: boolean;
      /** Is Analgesic Antiinflammatory */
      is_analgesic_antiinflammatory: boolean;
      /** Is Dermatological */
      is_dermatological: boolean;
      /** Is Narcotic */
      is_narcotic: boolean;
      /** Is Refill Restricted Patch */
      is_refill_restricted_patch: boolean;
      /** Forbids Refill */
      forbids_refill: boolean;
    };
    /**
     * MedicineInput
     * @description 処方薬品1明細の入力（JAHIS レコードNo.201 と紐づくレコード群）。
     */
    MedicineInput: {
      /** Line Number */
      line_number: number;
      /** Code Type */
      code_type: string;
      /** Name */
      name: string;
      /** Amount */
      amount: string;
      /** Unit */
      unit: string;
      /** Code */
      code?: string | null;
      unit_conversion?: components["schemas"]["UnitConversionInput"] | null;
      /**
       * Unequal Doses
       * @default []
       */
      unequal_doses: string[];
      /** Single Dose */
      single_dose?: string | null;
      substitution_restriction?:
        components["schemas"]["SubstitutionRestrictionInput"] | null;
      public_expense_burden?:
        components["schemas"]["PublicExpenseBurdenInput"] | null;
      /**
       * Supplements
       * @default []
       */
      supplements: components["schemas"]["MedicineSupplementInput"][];
    };
    /**
     * MedicineSupplementDto
     * @description 薬品補足（調製指示）の出力DTO。
     */
    MedicineSupplementDto: {
      /** Supplement Type */
      supplement_type: string;
      /** Text */
      text: string;
      /** Code */
      code: string | null;
    };
    /**
     * MedicineSupplementInput
     * @description 薬品補足のうち調製指示の入力（処方編 別表16 の 1・2・7）。
     */
    MedicineSupplementInput: {
      /** Supplement Type */
      supplement_type: string;
      /** Text */
      text: string;
      /** Code */
      code?: string | null;
    };
    /**
     * MediumCategoryDto
     * @description 中区分の出力DTO。
     */
    MediumCategoryDto: {
      /** Code */
      code: string;
      /** Major Category Code */
      major_category_code: string;
      /** Name */
      name: string;
      /** Display Order */
      display_order: number;
      /** Is Required */
      is_required: boolean;
      /** Is Enabled */
      is_enabled: boolean;
    };
    /**
     * MediumCategoryInput
     * @description 中区分定義の入力。
     */
    MediumCategoryInput: {
      /** Code */
      code: string;
      /** Major Category Code */
      major_category_code: string;
      /** Name */
      name: string;
      /** Display Order */
      display_order: number;
      /**
       * Is Required
       * @default false
       */
      is_required: boolean;
      /**
       * Is Enabled
       * @default true
       */
      is_enabled: boolean;
    };
    /**
     * MembershipRole
     * @description 招待や権限変更で指定できる法人内ロール。
     * @enum {string}
     */
    "MembershipRole-Input":
      "corporate_admin" | "store_operator" | "store_viewer";
    /**
     * MembershipRole
     * @description 法人内の固定ロール。
     * @enum {string}
     */
    "MembershipRole-Output":
      "corporate_admin" | "store_operator" | "store_viewer";
    /**
     * MembershipViewDto
     * @description 法人の利用者一覧・詳細で返す値。
     *
     *     法人アクセス権の状態と、その土台にある個人アカウントの状態は別物である。
     *     片方だけを返すと「権限は有効だがアカウントが停止中」という組み合わせを
     *     呼び出し側が区別できない。外部主体識別子は含めない。
     */
    MembershipViewDto: {
      /** Id */
      id: string;
      /** Account Id */
      account_id: string;
      /** Person Id */
      person_id: string;
      /** Corporate Id */
      corporate_id: string;
      status: components["schemas"]["AccountStatus-Output"];
      account_status: components["schemas"]["AccountStatus-Output"];
      role: components["schemas"]["MembershipRole-Output"];
      /** Store Ids */
      store_ids: string[];
      /** Staff Id */
      staff_id: string | null;
      /**
       * Suspended Store Ids
       * @default []
       */
      suspended_store_ids: string[];
    };
    /**
     * MergePatientsRequest
     * @description 患者名寄せ統合の入力。
     */
    MergePatientsRequest: {
      /** Target Patient Id */
      target_patient_id: string;
      /** Reason */
      reason: string;
    };
    /**
     * MergePatientsResultDto
     * @description 患者名寄せ統合の完了DTO。
     */
    MergePatientsResultDto: {
      /** Source Patient Id */
      source_patient_id: string;
      /** Target Patient Id */
      target_patient_id: string;
      /**
       * Merged At
       * Format: date-time
       */
      merged_at: string;
    };
    /**
     * NarcoticsRetailerLicenseDto
     * @description 麻薬小売業者免許の出力データ。
     */
    NarcoticsRetailerLicenseDto: {
      /** Number */
      number: string;
      /**
       * Valid From
       * Format: date
       */
      valid_from: string;
      /**
       * Valid To
       * Format: date
       */
      valid_to: string;
    };
    /**
     * NarcoticsRetailerLicenseRequest
     * @description 麻薬小売業者免許の入力モデル。
     */
    NarcoticsRetailerLicenseRequest: {
      /** Number */
      number: string;
      /**
       * Valid From
       * Format: date
       */
      valid_from: string;
      /**
       * Valid To
       * Format: date
       */
      valid_to: string;
    };
    /**
     * NsipsAdditionRequest
     * @description 構造化入力の算定加算情報。
     */
    NsipsAdditionRequest: {
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Points */
      points?: number | null;
      /** Quantity */
      quantity?: number | null;
    };
    /**
     * NsipsBundleRequest
     * @description 構造化入力のNSIPS Bundle。
     */
    NsipsBundleRequest: {
      /**
       * Header Version
       * @default unverified
       */
      header_version: string;
      patient: components["schemas"]["NsipsPatientRequest"];
      prescription: components["schemas"]["NsipsPrescriptionRequest"];
      /** Dispensed Date */
      dispensed_date?: string | null;
      insurance?: components["schemas"]["NsipsInsuranceRequest"] | null;
      /**
       * Additions
       * @default []
       */
      additions: components["schemas"]["NsipsAdditionRequest"][];
      /** Correction Kind */
      correction_kind?: ("update" | "delete") | null;
    };
    /**
     * NsipsInsuranceRequest
     * @description 構造化入力の保険・公費情報。
     */
    NsipsInsuranceRequest: {
      /** Insurer Number */
      insurer_number: string;
      /** Insured Symbol */
      insured_symbol: string;
      /** Insured Number */
      insured_number: string;
      /** Branch Number */
      branch_number?: string | null;
      /** Insured Type */
      insured_type?: ("self" | "family") | null;
      /** Benefit Ratio */
      benefit_ratio?: number | null;
      /** Public Payer Number 1 */
      public_payer_number_1?: string | null;
      /** Public Recipient Number 1 */
      public_recipient_number_1?: string | null;
      /** Public Payer Number 2 */
      public_payer_number_2?: string | null;
      /** Public Recipient Number 2 */
      public_recipient_number_2?: string | null;
    };
    /**
     * NsipsMedicineRequest
     * @description 構造化入力の薬品明細。
     */
    NsipsMedicineRequest: {
      /**
       * Medicine Code
       * @default
       */
      medicine_code: string;
      /** Medicine Name */
      medicine_name: string;
      /** Dosage */
      dosage: number | string;
      /** Unit */
      unit: string;
    };
    /**
     * NsipsPatientRequest
     * @description 構造化入力の患者情報。
     */
    NsipsPatientRequest: {
      /** External Patient Id */
      external_patient_id: string;
      /** Kanji Name */
      kanji_name: string;
      /** Kana Name */
      kana_name: string;
      /**
       * Birth Date
       * Format: date
       */
      birth_date: string;
      /** Gender */
      gender?: string | null;
      /** Postal Code */
      postal_code?: string | null;
      /** Address */
      address?: string | null;
      /** Phone Number */
      phone_number?: string | null;
    };
    /**
     * NsipsPrescriptionRequest
     * @description 構造化入力の処方情報。
     */
    NsipsPrescriptionRequest: {
      /** Document Number */
      document_number: string;
      /**
       * Issued Date
       * Format: date
       */
      issued_date: string;
      /** Institution Code */
      institution_code: string;
      /** Institution Name */
      institution_name: string;
      /** Department Code */
      department_code?: string | null;
      /** Department Name */
      department_name?: string | null;
      /** Doctor Name */
      doctor_name: string;
      /** Institution Prefecture Code */
      institution_prefecture_code?: string | null;
      /** Doctor Kana */
      doctor_kana?: string | null;
      /** Rps */
      rps: components["schemas"]["NsipsRpRequest"][];
      split_info?: components["schemas"]["NsipsSplitRequest"] | null;
    };
    /**
     * NsipsRpRequest
     * @description 構造化入力のRp。
     */
    NsipsRpRequest: {
      /** Rp Number */
      rp_number: number;
      /** Group Name */
      group_name: string;
      /** Instructions */
      instructions: string;
      /** Dispensing Quantity */
      dispensing_quantity: number;
      /** Medicines */
      medicines: components["schemas"]["NsipsMedicineRequest"][];
      /** Preparation Method */
      preparation_method?: string | null;
    };
    /**
     * NsipsSplitRequest
     * @description 構造化入力の分割調剤情報。
     */
    NsipsSplitRequest: {
      /** Iteration */
      iteration: number;
      /** Total Split Count */
      total_split_count: number;
      /** Split Reason */
      split_reason: string;
    };
    /**
     * Page
     * @description 一覧の1ページ分と、続きを引くためのカーソル。
     *
     *     ``dict[str, object]`` で返すと、項目名も要素の型も呼び出し側に伝わらず、
     *     OpenAPI にも自由形式のオブジェクトとしてしか載らない。生成したクライアントは
     *     一覧の中身を型として扱えなくなる。
     *
     *     ``next_cursor`` が ``None`` なら続きは無い。
     */
    Page_ManagerAssignmentDto_: {
      /** Items */
      items: components["schemas"]["ManagerAssignmentDto"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * Page
     * @description 一覧の1ページ分と、続きを引くためのカーソル。
     *
     *     ``dict[str, object]`` で返すと、項目名も要素の型も呼び出し側に伝わらず、
     *     OpenAPI にも自由形式のオブジェクトとしてしか載らない。生成したクライアントは
     *     一覧の中身を型として扱えなくなる。
     *
     *     ``next_cursor`` が ``None`` なら続きは無い。
     */
    Page_MembershipViewDto_: {
      /** Items */
      items: components["schemas"]["MembershipViewDto"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * Page
     * @description 一覧の1ページ分と、続きを引くためのカーソル。
     *
     *     ``dict[str, object]`` で返すと、項目名も要素の型も呼び出し側に伝わらず、
     *     OpenAPI にも自由形式のオブジェクトとしてしか載らない。生成したクライアントは
     *     一覧の中身を型として扱えなくなる。
     *
     *     ``next_cursor`` が ``None`` なら続きは無い。
     */
    Page_PendingExternalCorrectionDto_: {
      /** Items */
      items: components["schemas"]["PendingExternalCorrectionDto"][];
      /** Next Cursor */
      next_cursor?: string | null;
    };
    /**
     * PatientCoverageDto
     * @description 患者資格の出力データ（DTO）。
     */
    PatientCoverageDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Patient Id */
      patient_id: string;
      /** Coverage Type */
      coverage_type: string;
      /** Valid From */
      valid_from: string;
      /** Valid To */
      valid_to: string | null;
      /** Activated On */
      activated_on: string;
      /** Deactivated On */
      deactivated_on: string | null;
      /** Priority */
      priority: number;
      /** Insurer Number */
      insurer_number: string | null;
      /** Insured Symbol */
      insured_symbol: string | null;
      /** Insured Number */
      insured_number: string | null;
      /** Branch Number */
      branch_number: string | null;
      /** Insured Type */
      insured_type: string | null;
      /** Benefit Ratio */
      benefit_ratio: number | null;
      /** Payer Number */
      payer_number: string | null;
      /** Recipient Number */
      recipient_number: string | null;
    };
    /**
     * PatientDto
     * @description 患者詳細の出力データ（DTO）。
     */
    PatientDto: {
      /** Id */
      id: string;
      /** Patient Number */
      patient_number: number;
      /** Corporate Id */
      corporate_id: string;
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      /** Birth Date */
      birth_date: string | null;
      /** Gender */
      gender?: string | null;
      /** Postal Code */
      postal_code?: string | null;
      /** Address */
      address?: string | null;
      /** Phone Number */
      phone_number?: string | null;
      /**
       * Status
       * @default active
       */
      status: string;
      /** Merged Into Id */
      merged_into_id?: string | null;
      /**
       * Status History
       * @default []
       */
      status_history: components["schemas"]["PatientStatusChangeDto"][];
      /**
       * Profile History
       * @default []
       */
      profile_history: components["schemas"]["PatientProfileChangeDto"][];
    };
    /**
     * PatientExternalIdentifierDto
     * @description 外部患者ID対応付けの出力データ（DTO）。
     */
    PatientExternalIdentifierDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Patient Id */
      patient_id: string;
      /** System Name */
      system_name: string;
      /** External Patient Id */
      external_patient_id: string;
      /** Store Id */
      store_id: string | null;
      /** Is Active */
      is_active: boolean;
    };
    /**
     * PatientHeadingDto
     * @description 患者頭書きの現在値と変更履歴の応答。
     */
    PatientHeadingDto: {
      /** Patient Id */
      patient_id: string;
      /** Revision */
      revision: number;
      /** Summary */
      summary: string | null;
      /** Notes */
      notes: string | null;
      /** Updated By Person Id */
      updated_by_person_id: string | null;
      /** Updated By Account Id */
      updated_by_account_id: string | null;
      /** Updated At */
      updated_at: string | null;
      /** History */
      history: components["schemas"]["PatientHeadingRevisionDto"][];
    };
    /**
     * PatientHeadingRevisionDto
     * @description 患者頭書き1改訂分の応答。
     */
    PatientHeadingRevisionDto: {
      /** Revision */
      revision: number;
      /** Summary */
      summary: string | null;
      /** Notes */
      notes: string | null;
      /** Person Id */
      person_id: string;
      /** Account Id */
      account_id: string;
      /** Recorded At */
      recorded_at: string;
    };
    /**
     * PatientMedicalProfileDto
     * @description 頭書きの出力DTO。
     */
    PatientMedicalProfileDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Patient Id */
      patient_id: string;
      /** Allergies */
      allergies: components["schemas"]["AllergyDto"][];
      /** Adverse Reactions */
      adverse_reactions: components["schemas"]["AdverseReactionDto"][];
      /** Medical Conditions */
      medical_conditions: components["schemas"]["MedicalConditionDto"][];
      /** Concurrent Medications */
      concurrent_medications: components["schemas"]["ConcurrentMedicationDto"][];
      /** Active Concurrent Medications */
      active_concurrent_medications: components["schemas"]["ConcurrentMedicationDto"][];
      lifestyle: components["schemas"]["LifestyleDto"] | null;
      generic_preference: components["schemas"]["GenericPreferenceDto"] | null;
      family_pharmacist: components["schemas"]["FamilyPharmacistDto"] | null;
    };
    /**
     * PatientProfileChangeDto
     * @description 患者プロフィール変更履歴DTO。
     */
    PatientProfileChangeDto: {
      /** Recorded At */
      recorded_at: string;
      /** Changed Fields */
      changed_fields: string[];
      /**
       * Source
       * @default nsips
       */
      source: string;
      /** Reception Id */
      reception_id?: string | null;
      /** Store Id */
      store_id?: string | null;
      /** External Patient Id */
      external_patient_id?: string | null;
      received_profile?:
        components["schemas"]["PatientProfileSnapshotDto"] | null;
      before_profile?:
        components["schemas"]["PatientProfileSnapshotDto"] | null;
      applied_profile?:
        components["schemas"]["PatientProfileSnapshotDto"] | null;
      /** Person Id */
      person_id?: string | null;
      /** Account Id */
      account_id?: string | null;
    };
    /**
     * PatientProfileSnapshotDto
     * @description 患者プロフィールのある時点の値DTO。
     */
    PatientProfileSnapshotDto: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      /** Birth Date */
      birth_date: string | null;
      /** Gender */
      gender: string | null;
      /** Postal Code */
      postal_code: string | null;
      /** Address */
      address: string | null;
      /** Phone Number */
      phone_number: string | null;
    };
    /**
     * PatientStatusChangeDto
     * @description 患者状態変更履歴DTO。
     */
    PatientStatusChangeDto: {
      /** Before */
      before: string;
      /** After */
      after: string;
      /** Reason */
      reason: string;
      /** Person Id */
      person_id: string;
      /** Account Id */
      account_id: string;
      /** Recorded At */
      recorded_at: string;
      /** Merged Into Id */
      merged_into_id?: string | null;
    };
    /**
     * PendingExternalCorrectionDto
     * @description 未完了の外部訂正と薬歴参照情報。
     */
    PendingExternalCorrectionDto: {
      /** Record Id */
      record_id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Correction Id */
      correction_id: string;
      /** Correction Kind */
      correction_kind: string;
      /** Correction Status */
      correction_status: string;
      /** Source Document Number */
      source_document_number: string;
      /** Reason */
      reason: string;
      /** Details */
      details: string | null;
      /** Corrected At */
      corrected_at: string;
      /** Review Events */
      review_events: {
        [key: string]: string | null;
      }[];
    };
    /**
     * PersonNamesInput
     * @description 本人登録時に受け取る氏名の文字列。
     */
    PersonNamesInput: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
    };
    /**
     * PharmacyLicenseDto
     * @description 薬局開設許可の出力データ。
     */
    PharmacyLicenseDto: {
      /** Number */
      number: string;
      /**
       * Valid From
       * Format: date
       */
      valid_from: string;
      /**
       * Valid To
       * Format: date
       */
      valid_to: string;
    };
    /**
     * PharmacyLicenseRequest
     * @description 薬局開設許可の入力モデル。
     */
    PharmacyLicenseRequest: {
      /** Number */
      number: string;
      /**
       * Valid From
       * Format: date
       */
      valid_from: string;
      /**
       * Valid To
       * Format: date
       */
      valid_to: string;
    };
    /**
     * PolicySettingDto
     * @description ポリシー単一項目の出力データ。
     */
    PolicySettingDto: {
      /** Value */
      value: boolean;
      /** Overridable */
      overridable: boolean;
    };
    /**
     * PolicySettingRequest
     * @description ポリシー項目のリクエストモデル。
     */
    PolicySettingRequest: {
      /** Value */
      value: boolean;
      /** Overridable */
      overridable: boolean;
    };
    /**
     * PrescriberDto
     * @description 処方医の出力DTO。
     */
    PrescriberDto: {
      /** Full Name */
      full_name: string;
      /** Full Name Kana */
      full_name_kana: string | null;
      /** Code */
      code: string | null;
    };
    /**
     * PrescriberInput
     * @description 処方医の入力（JAHIS レコードNo.5）。
     */
    PrescriberInput: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string | null;
      /** First Name Kana */
      first_name_kana: string | null;
      /** Code */
      code?: string | null;
    };
    /**
     * PrescriberResponseDto
     * @description 疑義照会の回答の出力DTO。
     */
    PrescriberResponseDto: {
      /** Responded By */
      responded_by: string;
      /** Responded At */
      responded_at: string;
      /** Result Type */
      result_type: string;
      /** Content */
      content: string;
      /** Blocks Dispensing */
      blocks_dispensing: boolean;
    };
    /**
     * PrescriptionDto
     * @description 処方箋の出力DTO。
     */
    PrescriptionDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Source Type */
      source_type: string;
      /** Document Number */
      document_number: string;
      /** Status */
      status: string;
      medical_institution: components["schemas"]["MedicalInstitutionDto"];
      department: components["schemas"]["DepartmentDto"];
      prescriber: components["schemas"]["PrescriberDto"];
      period: components["schemas"]["PrescriptionPeriodDto"];
      /** Rps */
      rps: components["schemas"]["PrescriptionRpDto"][];
      management_info: components["schemas"]["PrescriptionManagementInfoDto"];
      /** Inquiries */
      inquiries: components["schemas"]["PrescriptionInquiryDto"][];
      /** Coverage Selection Record Id */
      coverage_selection_record_id: string | null;
      /** Has Open Inquiry */
      has_open_inquiry: boolean;
    };
    /**
     * PrescriptionInquiryDto
     * @description 疑義照会1件の出力DTO。
     */
    PrescriptionInquiryDto: {
      /** Inquiry Number */
      inquiry_number: number;
      /** Pharmacist Id */
      pharmacist_id: string;
      /** Inquired At */
      inquired_at: string;
      /** Category */
      category: string;
      /** Content */
      content: string;
      response: components["schemas"]["PrescriberResponseDto"] | null;
      /** Is Open */
      is_open: boolean;
    };
    /**
     * PrescriptionManagementInfoDto
     * @description 管理情報・特殊指示の出力DTO。
     */
    PrescriptionManagementInfoDto: {
      /** Refill Count */
      refill_count: number | null;
      /** Split Total Count */
      split_total_count: number | null;
      /** Split Iteration */
      split_iteration: number | null;
      /** Residual Drug Instruction */
      residual_drug_instruction: string | null;
      /** Narcotic License Number */
      narcotic_license_number: string | null;
      /** Patient Address */
      patient_address: string | null;
      /** Patient Phone Number */
      patient_phone_number: string | null;
      /** Notes */
      notes: string[];
      /** Clinical Info */
      clinical_info: string[];
      /** Lab Data */
      lab_data: string[];
    };
    /**
     * PrescriptionManagementInput
     * @description 処方箋の管理情報・特殊指示の入力。
     *
     *     麻薬処方箋情報とリフィル指示はここで受け取れるが、いずれも医薬品マスタの
     *     裏付けが要る（``NarcoticPrescriptionService`` / ``RefillEligibilityService``）。
     *     マスタが無い間、これらを含む処方箋の登録は fail-closed で失敗する。
     */
    PrescriptionManagementInput: {
      /** Refill Count */
      refill_count?: number | null;
      /** Split Total Count */
      split_total_count?: number | null;
      /** Split Iteration */
      split_iteration?: number | null;
      /** Residual Drug Instruction */
      residual_drug_instruction?: string | null;
      /** Narcotic License Number */
      narcotic_license_number?: string | null;
      /** Patient Address */
      patient_address?: string | null;
      /** Patient Phone Number */
      patient_phone_number?: string | null;
      /** Notes */
      notes?: string[];
      /** Clinical Info */
      clinical_info?: string[];
      /** Lab Data */
      lab_data?: string[];
    };
    /**
     * PrescriptionMedicineDto
     * @description 処方薬品1明細の出力DTO。
     */
    PrescriptionMedicineDto: {
      /** Line Number */
      line_number: number;
      /** Code Type */
      code_type: string;
      /** Code */
      code: string | null;
      /** Name */
      name: string;
      /** Amount */
      amount: string;
      /** Unit */
      unit: string;
      /** Single Dose */
      single_dose: string | null;
      /** Unequal Doses */
      unequal_doses: string[];
      unit_conversion: components["schemas"]["UnitConversionDto"] | null;
      substitution_restriction:
        components["schemas"]["SubstitutionRestrictionDto"] | null;
      public_expense_burden:
        components["schemas"]["PublicExpenseBurdenDto"] | null;
      /** Supplements */
      supplements: components["schemas"]["MedicineSupplementDto"][];
    };
    /**
     * PrescriptionPeriodDto
     * @description 交付日と使用期限の出力DTO。
     */
    PrescriptionPeriodDto: {
      /** Issued Date */
      issued_date: string;
      /** Valid To */
      valid_to: string;
    };
    /**
     * PrescriptionRpDto
     * @description 剤（Rp）の出力DTO。
     */
    PrescriptionRpDto: {
      /** Rp Number */
      rp_number: number;
      /** Category */
      category: string;
      /** Quantity */
      quantity: number;
      dosage_instruction: components["schemas"]["DosageInstructionDto"];
      /** Medicines */
      medicines: components["schemas"]["PrescriptionMedicineDto"][];
      /** Custom Category Name */
      custom_category_name: string | null;
      /** Dosage Supplements */
      dosage_supplements: components["schemas"]["DosageSupplementDto"][];
    };
    /**
     * ProfileUpdateInput
     * @description 1回の服薬指導が頭書きへ加える差分の入力。
     */
    ProfileUpdateInput: {
      /** New Allergies */
      new_allergies?: components["schemas"]["AllergyIntentInput"][];
      /** Retracted Allergies */
      retracted_allergies?: components["schemas"]["RetractAllergyIntentInput"][];
      /** New Adverse Reactions */
      new_adverse_reactions?: components["schemas"]["AdverseReactionIntentInput"][];
      /** Retracted Adverse Reactions */
      retracted_adverse_reactions?: components["schemas"]["RetractAdverseReactionIntentInput"][];
      /** New Conditions */
      new_conditions?: components["schemas"]["ConditionIntentInput"][];
      /** Updated Conditions */
      updated_conditions?: components["schemas"]["UpdateConditionStatusIntentInput"][];
      /** Retracted Conditions */
      retracted_conditions?: components["schemas"]["RetractConditionIntentInput"][];
      /** New Concurrent Medications */
      new_concurrent_medications?: components["schemas"]["ConcurrentMedicationIntentInput"][];
      /** Stopped Concurrent Medications */
      stopped_concurrent_medications?: components["schemas"]["StopConcurrentMedicationIntentInput"][];
      /** Lifestyle Note */
      lifestyle_note?: string | null;
      /** Generic Preference */
      generic_preference?: string | null;
      /** Family Pharmacist Id */
      family_pharmacist_id?: string | null;
      /** Family Pharmacist Agreed On */
      family_pharmacist_agreed_on?: string | null;
    };
    /**
     * ProvenanceDto
     * @description 頭書き要素の由来の出力DTO。
     */
    ProvenanceDto: {
      /** Source Record Id */
      source_record_id: string;
      /** Recorded By */
      recorded_by: string;
      /** Recorded On */
      recorded_on: string;
    };
    /**
     * PublicExpenseBurdenDto
     * @description 公費負担区分の出力DTO。
     */
    PublicExpenseBurdenDto: {
      /** First */
      first: boolean;
      /** Second */
      second: boolean;
      /** Third */
      third: boolean;
      /** Special */
      special: boolean;
    };
    /**
     * PublicExpenseBurdenInput
     * @description 公費負担区分の入力（JAHIS レコードNo.231）。
     */
    PublicExpenseBurdenInput: {
      /**
       * First
       * @default false
       */
      first: boolean;
      /**
       * Second
       * @default false
       */
      second: boolean;
      /**
       * Third
       * @default false
       */
      third: boolean;
      /**
       * Special
       * @default false
       */
      special: boolean;
    };
    /**
     * PublicExpenseCoverageSelectionDto
     * @description 公費枠の出力DTO。選択元IDと請求固定値を束ねたまま返す。
     */
    PublicExpenseCoverageSelectionDto: {
      /** Source Coverage Id */
      source_coverage_id: string;
      /** Priority */
      priority: number;
      /** Payer Number */
      payer_number: string;
      /** Recipient Number */
      recipient_number: string;
    };
    /**
     * QualificationsRequest
     * @description 資格の入力。項目を省くと、その資格を持たないものとして上書きする。
     */
    QualificationsRequest: {
      /** Pharmacist License Number */
      pharmacist_license_number?: string | null;
      /** Insurance Pharmacist Registration Number */
      insurance_pharmacist_registration_number?: string | null;
      /** Insurance Pharmacist Registration Date */
      insurance_pharmacist_registration_date?: string | null;
      /** Registered Seller Number */
      registered_seller_number?: string | null;
      /** Dietitian Registration Number */
      dietitian_registration_number?: string | null;
      /**
       * Is Registered Dietitian
       * @default true
       */
      is_registered_dietitian: boolean;
    };
    /**
     * QuantityAdjustmentDto
     * @description 減数調剤の出力DTO。
     */
    QuantityAdjustmentDto: {
      /** Prescribed Quantity */
      prescribed_quantity: number;
      /** Reason */
      reason: string;
      /** Inquiry Number */
      inquiry_number?: number | null;
    };
    /**
     * QuantityAdjustmentInput
     * @description 軸2: 減数調剤の入力。処方時の数量を併せて受け取る。
     */
    QuantityAdjustmentInput: {
      /** Prescribed Quantity */
      prescribed_quantity: number;
      /** Reason */
      reason: string;
      /** Inquiry Number */
      inquiry_number?: number | null;
    };
    /**
     * ReactivatePatientRequest
     * @description 患者再有効化の入力。
     */
    ReactivatePatientRequest: {
      /** Reason */
      reason: string;
    };
    /**
     * RebuildMedicalProfileRequest
     * @description 頭書きの再構築の入力。
     */
    RebuildMedicalProfileRequest: {
      /**
       * As Of
       * Format: date
       */
      as_of: string;
    };
    /**
     * RecordAuditRequest
     * @description 監査の入力。
     */
    RecordAuditRequest: {
      /** Has Issues */
      has_issues: boolean;
      /** Notes */
      notes?: string | null;
    };
    /**
     * RecordCoverageSelectionRequest
     * @description 受付時の資格選択の入力。
     */
    RecordCoverageSelectionRequest: {
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /**
       * Applied On
       * Format: date
       */
      applied_on: string;
      /** Coverage Ids */
      coverage_ids: string[];
    };
    /**
     * RecordDispensedContentRequest
     * @description 調剤内容の記録の入力。送った内容で調剤内容を置き換える。
     */
    RecordDispensedContentRequest: {
      /** Dispensed Rps */
      dispensed_rps: components["schemas"]["DispensedRpInput"][];
    };
    /**
     * RecordTracingReportRequest
     * @description トレーシングレポート記録の入力。
     */
    RecordTracingReportRequest: {
      /**
       * Provided At
       * Format: date-time
       */
      provided_at: string;
      /** Medical Institution Name */
      medical_institution_name: string;
      /** Physician Name */
      physician_name: string;
      /** Category */
      category: string;
      /** Fee Category */
      fee_category: string;
      /** Delivery Method */
      delivery_method: string;
      /** Content */
      content: string;
    };
    /**
     * RecordTracingReportResponseRequest
     * @description トレーシングレポート医師返答の入力。
     */
    RecordTracingReportResponseRequest: {
      /**
       * Responded At
       * Format: date-time
       */
      responded_at: string;
      /** Content */
      content: string;
      /** Action Type */
      action_type: string;
      /** Received By */
      received_by: string;
      /** Acknowledged Physician Name */
      acknowledged_physician_name?: string | null;
    };
    /**
     * RegisterContractRequest
     * @description 新規契約の法人と初期管理者を一括登録する入力。
     */
    RegisterContractRequest: {
      /** Name */
      name: string;
      /** Representative Last Name */
      representative_last_name: string;
      /** Representative First Name */
      representative_first_name: string;
      administrator: components["schemas"]["PersonNamesInput"];
      /** Email */
      email: string;
      /** Initial Password */
      initial_password: string;
    };
    /**
     * RegisterCorporateRequest
     * @description 法人登録の入力。
     */
    RegisterCorporateRequest: {
      /** Name */
      name: string;
      /** Representative Last Name */
      representative_last_name: string;
      /** Representative First Name */
      representative_first_name: string;
    };
    /**
     * RegisterCoverageRequest
     * @description 資格登録の入力。
     *
     *     ``valid_from`` / ``valid_to`` は終了日を含む閉区間、``activated_on`` は
     *     無効化発効日を含まない区間の開始である。実効期間は両者の交差になる。
     */
    RegisterCoverageRequest: {
      /** Coverage Type */
      coverage_type: string;
      /**
       * Valid From
       * Format: date
       */
      valid_from: string;
      /**
       * Activated On
       * Format: date
       */
      activated_on: string;
      /** Valid To */
      valid_to?: string | null;
      /**
       * Priority
       * @default 1
       */
      priority: number;
      /** Insurer Number */
      insurer_number?: string | null;
      /** Insured Symbol */
      insured_symbol?: string | null;
      /** Insured Number */
      insured_number?: string | null;
      /** Branch Number */
      branch_number?: string | null;
      /** Insured Type */
      insured_type?: string | null;
      /** Benefit Ratio */
      benefit_ratio?: number | null;
      /** Payer Number */
      payer_number?: string | null;
      /** Recipient Number */
      recipient_number?: string | null;
    };
    /**
     * RegisterExternalIdentifierRequest
     * @description 外部患者IDの登録の入力。
     */
    RegisterExternalIdentifierRequest: {
      /** System Name */
      system_name: string;
      /** External Patient Id */
      external_patient_id: string;
      /** Store Id */
      store_id?: string | null;
    };
    /**
     * RegisterMedicineRequest
     * @description 医薬品の取り込みの入力。収載期間は終了日を含む閉区間として扱う。
     */
    RegisterMedicineRequest: {
      /** Code Type */
      code_type: string;
      /** Code */
      code: string;
      /** Name */
      name: string;
      /** Unit */
      unit: string;
      /** Dosage Form */
      dosage_form: string;
      /**
       * Listed On
       * Format: date
       */
      listed_on: string;
      /**
       * Catalog Version
       * Format: date
       */
      catalog_version: string;
      /** Withdrawn On */
      withdrawn_on?: string | null;
      /**
       * Narcotic Category
       * @default none
       */
      narcotic_category: string;
      /**
       * Generic Category
       * @default other
       */
      generic_category: string;
      /**
       * Has Dosage Limit
       * @default false
       */
      has_dosage_limit: boolean;
      /**
       * Is Analgesic Antiinflammatory
       * @default false
       */
      is_analgesic_antiinflammatory: boolean;
      /**
       * Is Dermatological
       * @default false
       */
      is_dermatological: boolean;
    };
    /**
     * RegisterPatientRequest
     * @description 患者登録の入力。
     */
    RegisterPatientRequest: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      /** Birth Date */
      birth_date?: string | null;
    };
    /**
     * RegisterPersonRequest
     * @description 自法人の本人を登録する。
     */
    RegisterPersonRequest: {
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
    };
    /**
     * RegisterPrescriptionRequest
     * @description 処方箋登録の入力。
     */
    RegisterPrescriptionRequest: {
      /** Store Id */
      store_id: string;
      /** Patient Id */
      patient_id: string;
      /** Source Type */
      source_type: string;
      /** Document Number */
      document_number: string;
      /**
       * Issued Date
       * Format: date
       */
      issued_date: string;
      medical_institution: components["schemas"]["MedicalInstitutionInput"];
      department: components["schemas"]["DepartmentInput"];
      prescriber: components["schemas"]["PrescriberInput"];
      /** Rps */
      rps: components["schemas"]["RpInput"][];
      /** Valid To */
      valid_to?: string | null;
      management_info?:
        components["schemas"]["PrescriptionManagementInput"] | null;
      /** Coverage Selection Record Id */
      coverage_selection_record_id?: string | null;
    };
    /**
     * RegisterStaffForAdminRequest
     * @description 初期管理者へのスタッフ登録入力。
     */
    RegisterStaffForAdminRequest: {
      /** Last Name */
      last_name?: string | null;
      /** First Name */
      first_name?: string | null;
      /** Last Name Kana */
      last_name_kana?: string | null;
      /** First Name Kana */
      first_name_kana?: string | null;
      /** Code */
      code?: string | null;
      /** Job Title */
      job_title?: string | null;
      /** Phone Number */
      phone_number?: string | null;
      /** Email */
      email?: string | null;
      /** Initial Home Store Id */
      initial_home_store_id?: string | null;
      /** Initial Start Date */
      initial_start_date?: string | null;
      /** Pharmacist License Number */
      pharmacist_license_number?: string | null;
      /** Insurance Pharmacist Registration Number */
      insurance_pharmacist_registration_number?: string | null;
      /** Insurance Pharmacist Registration Date */
      insurance_pharmacist_registration_date?: string | null;
      /** Registered Seller Number */
      registered_seller_number?: string | null;
      /** Dietitian Registration Number */
      dietitian_registration_number?: string | null;
      /**
       * Is Registered Dietitian
       * @default true
       */
      is_registered_dietitian: boolean;
    };
    /**
     * RegisterStaffRequest
     * @description スタッフ登録の入力。
     */
    RegisterStaffRequest: {
      /** Pharmacist License Number */
      pharmacist_license_number?: string | null;
      /** Insurance Pharmacist Registration Number */
      insurance_pharmacist_registration_number?: string | null;
      /** Insurance Pharmacist Registration Date */
      insurance_pharmacist_registration_date?: string | null;
      /** Registered Seller Number */
      registered_seller_number?: string | null;
      /** Dietitian Registration Number */
      dietitian_registration_number?: string | null;
      /**
       * Is Registered Dietitian
       * @default true
       */
      is_registered_dietitian: boolean;
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      account: components["schemas"]["StaffAccountRequest"];
      /** Job Title */
      job_title?: string | null;
      /** Code */
      code?: string | null;
      /** Phone Number */
      phone_number?: string | null;
      /** Email */
      email?: string | null;
      /** Initial Home Store Id */
      initial_home_store_id?: string | null;
      /** Initial Start Date */
      initial_start_date?: string | null;
    };
    /**
     * RegisterStoreRequest
     * @description 店舗登録の入力。
     */
    RegisterStoreRequest: {
      /** Name */
      name: string;
      /** Name Kana */
      name_kana: string;
      /** Postal Code */
      postal_code: string;
      /** Address */
      address: string;
      /** Phone Number */
      phone_number: string;
      /** Name Romaji */
      name_romaji?: string | null;
      /** Fax Number */
      fax_number?: string | null;
      /** Email */
      email?: string | null;
      /** Code */
      code?: string | null;
      /** Insurance Pharmacy Number */
      insurance_pharmacy_number?: string | null;
    };
    /**
     * RegisteredContract
     * @description 登録を完了した契約の識別子。
     */
    RegisteredContract: {
      /** Id */
      id: string;
      /** Account Id */
      account_id: string;
      /** Email */
      email: string;
    };
    /**
     * RegisteredIdResponse
     * @description 新規登録で採番されたIDだけを返す応答。
     */
    RegisteredIdResponse: {
      /** Id */
      id: string;
    };
    /**
     * RelatedEventCandidateDto
     * @description 関連Eventとして選べる最小限の情報。
     */
    RelatedEventCandidateDto: {
      /** Event Id */
      event_id: string;
      /** Store Id */
      store_id: string;
      /** Event Type Name */
      event_type_name: string;
      /** Occurred At */
      occurred_at: string | null;
      /** Occurred At Is Unknown */
      occurred_at_is_unknown: boolean;
      /** Created At */
      created_at: string;
    };
    /**
     * ReplaceManagerRequest
     * @description 管理薬剤師交代の入力。
     */
    ReplaceManagerRequest: {
      /** Current Assignment Id */
      current_assignment_id: string;
      /** New Staff Id */
      new_staff_id: string;
      /**
       * Effective On
       * Format: date
       */
      effective_on: string;
    };
    /**
     * ResidualDrugDto
     * @description 残薬状況の出力DTO。
     */
    ResidualDrugDto: {
      /** Has Residual Drugs */
      has_residual_drugs: boolean;
      /** Quantity */
      quantity: number | null;
      /** Reason */
      reason: string | null;
    };
    /**
     * ResidualDrugInput
     * @description 残薬状況の入力（法定記載事項ウ（ホ））。
     */
    ResidualDrugInput: {
      /** Has Residual Drugs */
      has_residual_drugs: boolean;
      /** Quantity */
      quantity?: number | null;
      /** Reason */
      reason?: string | null;
    };
    /**
     * ResolveInquiryRequest
     * @description 疑義照会の回答の入力。
     */
    ResolveInquiryRequest: {
      /** Responded By */
      responded_by: string;
      /** Result Type */
      result_type: string;
      /** Content */
      content: string;
    };
    /**
     * RetireStaffRequest
     * @description 退職の入力。退職日以降に及ぶ所属はこの日で打ち切られる。
     */
    RetireStaffRequest: {
      /**
       * Retired On
       * Format: date
       */
      retired_on: string;
    };
    /**
     * RetractAdverseReactionIntentInput
     * @description 取り消す副作用歴の入力。
     */
    RetractAdverseReactionIntentInput: {
      /** Medicine Name */
      medicine_name: string;
      /** Reason */
      reason?: string | null;
    };
    /**
     * RetractAllergyIntentInput
     * @description 取り消すアレルギー歴の入力。
     */
    RetractAllergyIntentInput: {
      /** Allergen */
      allergen: string;
      /** Reason */
      reason?: string | null;
    };
    /**
     * RetractConditionIntentInput
     * @description 取り消す疾患の入力。
     */
    RetractConditionIntentInput: {
      /** Condition Name */
      condition_name: string;
      /** Reason */
      reason?: string | null;
    };
    /**
     * ReviewExternalPrescriptionCorrectionRequest
     * @description 外部訂正判断の入力。監査担当者と処理時刻は指定できない。
     */
    ReviewExternalPrescriptionCorrectionRequest: {
      /**
       * Decision
       * @enum {string}
       */
      decision:
        | "amend"
        | "no_action"
        | "investigating"
        | "match_reregistered_prescription";
      /** Reason */
      reason: string;
      amended_soap?: components["schemas"]["SoapInput"] | null;
      /** Matched Prescription Id */
      matched_prescription_id?: string | null;
    };
    /**
     * RpInput
     * @description 剤（Rp）の入力（JAHIS レコードNo.101 / No.111 / No.181）。
     */
    RpInput: {
      /** Rp Number */
      rp_number: number;
      /** Category */
      category: string;
      /** Quantity */
      quantity: number;
      dosage_instruction: components["schemas"]["DosageInstructionInput"];
      /** Medicines */
      medicines: components["schemas"]["MedicineInput"][];
      /** Custom Category Name */
      custom_category_name?: string | null;
      /**
       * Dosage Supplements
       * @default []
       */
      dosage_supplements: components["schemas"]["DosageSupplementInput"][];
    };
    /**
     * SelectStoreContextRequest
     * @description 作業対象とする店舗の選択入力。
     */
    SelectStoreContextRequest: {
      /** Store Id */
      store_id: string;
    };
    /**
     * SelectableStoreDto
     * @description 現在選択可能な店舗の表示値。
     */
    SelectableStoreDto: {
      /** Id */
      id: string;
      /** Name */
      name: string;
      /** Code */
      code?: string | null;
    };
    /**
     * ServiceStatusResponse
     * @description 稼働状態の応答。
     */
    ServiceStatusResponse: {
      /** Status */
      status: string;
    };
    /**
     * SoapDto
     * @description SOAPの出力DTO。
     */
    SoapDto: {
      /** Subjective */
      subjective: components["schemas"]["LabeledNoteDto"][];
      /** Objective */
      objective: components["schemas"]["LabeledNoteDto"][];
      /** Assessment */
      assessment: components["schemas"]["LabeledNoteDto"][];
      /** Plan */
      plan: components["schemas"]["LabeledNoteDto"][];
    };
    /**
     * SoapInput
     * @description SOAP各セクションの入力。
     */
    SoapInput: {
      /** Subjective */
      subjective?: components["schemas"]["LabeledNoteInput"][];
      /** Objective */
      objective?: components["schemas"]["LabeledNoteInput"][];
      /** Assessment */
      assessment?: components["schemas"]["LabeledNoteInput"][];
      /** Plan */
      plan?: components["schemas"]["LabeledNoteInput"][];
    };
    /**
     * StaffAccountRequest
     * @description スタッフと同時に生成するアカウントの入力。
     */
    StaffAccountRequest: {
      /** Email */
      email: string;
      /** Password */
      password: string;
      /**
       * Role
       * @default store_operator
       */
      role: string;
      /** Store Ids */
      store_ids?: string[] | null;
    };
    /**
     * StaffDto
     * @description スタッフ詳細の出力データ（DTO）。
     */
    StaffDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      /** Job Title */
      job_title: string | null;
      /** Code */
      code: string | null;
      /** Phone Number */
      phone_number: string | null;
      /** Email */
      email: string | null;
      /** Is Active */
      is_active: boolean;
      /** Is Pharmacist */
      is_pharmacist: boolean;
      /** Is Dietitian */
      is_dietitian: boolean;
      /** Is Registered Seller */
      is_registered_seller: boolean;
      /** Current Home Store Id */
      current_home_store_id: string | null;
    };
    /**
     * StaffSummaryDto
     * @description スタッフ一覧の出力データ（DTO）。
     */
    StaffSummaryDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Last Name */
      last_name: string;
      /** First Name */
      first_name: string;
      /** Last Name Kana */
      last_name_kana: string;
      /** First Name Kana */
      first_name_kana: string;
      /** Code */
      code: string | null;
      /** Job Title */
      job_title: string | null;
      /** Is Active */
      is_active: boolean;
      /** Is Pharmacist */
      is_pharmacist: boolean;
    };
    /**
     * StartDispensingRequest
     * @description 調剤開始の入力。
     */
    StartDispensingRequest: {
      /** Store Id */
      store_id: string;
      /** Prescription Id */
      prescription_id: string;
      /** Iteration */
      iteration: number;
      /**
       * Dispensed Date
       * Format: date
       */
      dispensed_date: string;
      /** Dispensed Rps */
      dispensed_rps: components["schemas"]["DispensedRpInput"][];
      /** Split Reason */
      split_reason?: string | null;
      /** Total Split Count */
      total_split_count?: number | null;
    };
    /**
     * StartEventMedicationHistoryRequest
     * @description 既存Eventから薬歴下書きを起こす入力。
     */
    StartEventMedicationHistoryRequest: {
      soap?: components["schemas"]["SoapInput"];
      /** Method */
      method?: string | null;
      handbook_status?: components["schemas"]["HandbookStatusInput"] | null;
      residual_drug?: components["schemas"]["ResidualDrugInput"] | null;
      /** Information Sheet Provided */
      information_sheet_provided?: boolean | null;
      profile_updates?: components["schemas"]["ProfileUpdateInput"] | null;
      /**
       * Additional Notes
       * @default []
       */
      additional_notes: components["schemas"]["CategorizedNoteInput"][];
      /** Counseled At */
      counseled_at?: string | null;
    };
    /**
     * StartInquiryRequest
     * @description 疑義照会の開始の入力。
     */
    StartInquiryRequest: {
      /** Category */
      category: string;
      /** Content */
      content: string;
    };
    /**
     * StartMedicationHistoryRequest
     * @description 薬歴の初回保存の入力。
     */
    StartMedicationHistoryRequest: {
      /** Store Id */
      store_id: string;
      /** Dispensing Id */
      dispensing_id: string;
      /** Reception Id */
      reception_id?: string | null;
      soap?: components["schemas"]["SoapInput"];
      /** Method */
      method?: string | null;
      handbook_status?: components["schemas"]["HandbookStatusInput"] | null;
      residual_drug?: components["schemas"]["ResidualDrugInput"] | null;
      /** Information Sheet Provided */
      information_sheet_provided?: boolean | null;
      profile_updates?: components["schemas"]["ProfileUpdateInput"] | null;
      /** Counseled At */
      counseled_at?: string | null;
      /**
       * Occurred At
       * Format: date-time
       */
      occurred_at: string;
    };
    /**
     * StatutoryItemAssessmentDto
     * @description 記載事項1つの判定結果の出力DTO。
     */
    StatutoryItemAssessmentDto: {
      /** Item */
      item: string;
      /** Item Label */
      item_label: string;
      /** Article Clause */
      article_clause: string;
      /** State */
      state: string;
      /** State Label */
      state_label: string;
    };
    /**
     * StatutoryRecordBlockerDto
     * @description 調剤録の代替を妨げる要因の出力DTO。
     */
    StatutoryRecordBlockerDto: {
      /** Blocker */
      blocker: string;
      /** Blocker Label */
      blocker_label: string;
    };
    /**
     * StatutoryRecordSufficiencyDto
     * @description 調剤録の代替可否の出力DTO。
     */
    StatutoryRecordSufficiencyDto: {
      /** Record Id */
      record_id: string;
      /** Dispensing Id */
      dispensing_id: string;
      /** Prescription Id */
      prescription_id: string;
      /** Substitutes Dispensing Record */
      substitutes_dispensing_record: boolean;
      /** Assessments */
      assessments: components["schemas"]["StatutoryItemAssessmentDto"][];
      /** Blockers */
      blockers: components["schemas"]["StatutoryRecordBlockerDto"][];
      /** Missing Items */
      missing_items: string[];
    };
    /**
     * StopConcurrentMedicationIntentInput
     * @description 聞き取った併用薬の終了の入力。
     */
    StopConcurrentMedicationIntentInput: {
      /** Medicine Name */
      medicine_name: string;
      /**
       * Ended On
       * Format: date
       */
      ended_on: string;
    };
    /**
     * StoreDto
     * @description 店舗詳細の出力データ（DTO）
     */
    StoreDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Name */
      name: string;
      /** Name Kana */
      name_kana: string;
      /** Name Romaji */
      name_romaji: string | null;
      /** Postal Code */
      postal_code: string;
      /** Address */
      address: string;
      /** Phone Number */
      phone_number: string;
      /** Fax Number */
      fax_number: string | null;
      /** Email */
      email: string | null;
      /** Code */
      code: string | null;
      /** Insurance Pharmacy Number */
      insurance_pharmacy_number: string | null;
      /** Status */
      status: string;
      /** Status History */
      status_history: components["schemas"]["StoreStatusChangeDto"][];
      business_hours: components["schemas"]["BusinessHoursDto"] | null;
      licenses?: components["schemas"]["StoreLicensesDto"] | null;
      policy?: components["schemas"]["StorePolicyDto"] | null;
    };
    /**
     * StoreLicensesDto
     * @description 店舗許認可の出力データ。
     */
    StoreLicensesDto: {
      pharmacy_license: components["schemas"]["PharmacyLicenseDto"];
      narcotics_retailer_license?:
        components["schemas"]["NarcoticsRetailerLicenseDto"] | null;
    };
    /**
     * StoreOpeningStatusDto
     * @description ある日時の開局状況。
     *
     *     判定に使った業務日と時刻を必ず返す。呼び出し側が自分の時計で「今」を作り
     *     直すと、タイムゾーンの違いでずれた時刻の答えを受け取ったことに気づけない。
     */
    StoreOpeningStatusDto: {
      /** Store Id */
      store_id: string;
      /** State */
      state: string;
      /**
       * On
       * Format: date
       */
      on: string;
      /**
       * At
       * Format: time
       */
      at: string;
      /** Slots */
      slots: components["schemas"]["BusinessHourSlotDto"][];
    };
    /**
     * StorePolicyDto
     * @description 店舗ポリシーの出力データ。
     */
    StorePolicyDto: {
      /** Require Prescription Audit */
      require_prescription_audit?: boolean | null;
      /** Prohibit Self Verification */
      prohibit_self_verification?: boolean | null;
    };
    /**
     * StoreStatusChangeDto
     * @description 状態履歴の公開値。
     */
    StoreStatusChangeDto: {
      /** Before */
      before: string;
      /** After */
      after: string;
      /** Reason */
      reason: string;
      /** Person Id */
      person_id: string;
      /** Account Id */
      account_id: string;
      /**
       * Recorded At
       * Format: date-time
       */
      recorded_at: string;
    };
    /**
     * StoreSummaryDto
     * @description 店舗一覧の出力データ（DTO）。
     */
    StoreSummaryDto: {
      /** Id */
      id: string;
      /** Corporate Id */
      corporate_id: string;
      /** Name */
      name: string;
      /** Name Kana */
      name_kana: string;
      /** Code */
      code: string | null;
    };
    /**
     * SubstitutionDto
     * @description 代替調剤の出力DTO。
     */
    SubstitutionDto: {
      /** Category */
      category: string;
      /** Original Code Type */
      original_code_type: string;
      /** Original Code */
      original_code: string | null;
      /** Original Name */
      original_name: string;
      /** Reason */
      reason: string | null;
      /** Inquiry Number */
      inquiry_number?: number | null;
    };
    /**
     * SubstitutionInput
     * @description 軸1: 代替調剤の入力。処方薬品そのものを置き換えたときだけ指定する。
     */
    SubstitutionInput: {
      /** Category */
      category: string;
      /** Original Code Type */
      original_code_type: string;
      /** Original Name */
      original_name: string;
      /** Original Code */
      original_code?: string | null;
      /** Reason */
      reason?: string | null;
      /** Inquiry Number */
      inquiry_number?: number | null;
    };
    /**
     * SubstitutionRestrictionDto
     * @description 変更制限の出力DTO。
     */
    SubstitutionRestrictionDto: {
      /** Restriction Type */
      restriction_type: string;
      /** Reason */
      reason: string | null;
      /** Forbids Generic Substitution */
      forbids_generic_substitution: boolean;
    };
    /**
     * SubstitutionRestrictionInput
     * @description 薬品補足のうち変更制限の入力（処方編 別表16 の 3〜6・8）。
     */
    SubstitutionRestrictionInput: {
      /** Restriction Type */
      restriction_type: string;
      /** Reason */
      reason?: string | null;
    };
    /**
     * TracingReportDto
     * @description 処方医への服薬情報等提供（トレーシングレポート）出力DTO。
     */
    TracingReportDto: {
      /** Id */
      id: string;
      /** Reporter Id */
      reporter_id: string;
      /** Provided At */
      provided_at: string;
      /** Medical Institution Name */
      medical_institution_name: string;
      /** Physician Name */
      physician_name: string;
      /** Category */
      category: string;
      /** Fee Category */
      fee_category: string;
      /** Delivery Method */
      delivery_method: string;
      /** Content */
      content: string;
      response?: components["schemas"]["TracingReportResponseDto"] | null;
    };
    /**
     * TracingReportResponseDto
     * @description トレーシングレポートに対する処方医返答の出力DTO。
     */
    TracingReportResponseDto: {
      /** Responded At */
      responded_at: string;
      /** Action Type */
      action_type: string;
      /** Content */
      content: string;
      /** Received By */
      received_by: string;
      /** Acknowledged Physician Name */
      acknowledged_physician_name?: string | null;
    };
    /**
     * TransferHomeStoreRequest
     * @description 主所属の異動の入力。
     */
    TransferHomeStoreRequest: {
      /** Store Id */
      store_id: string;
      /**
       * Transfer Date
       * Format: date
       */
      transfer_date: string;
    };
    /**
     * UnitConversionDto
     * @description 単位変換の出力DTO。
     */
    UnitConversionDto: {
      /** Factor */
      factor: string;
      /** Tariff Unit */
      tariff_unit: string;
    };
    /**
     * UnitConversionInput
     * @description 単位変換の入力（JAHIS レコードNo.211）。
     */
    UnitConversionInput: {
      /** Factor */
      factor: string;
      /** Tariff Unit */
      tariff_unit: string;
    };
    /**
     * UpdateCategoryCatalogRequest
     * @description 区分カタログの更新入力。
     */
    UpdateCategoryCatalogRequest: {
      /**
       * Major Categories
       * @default []
       */
      major_categories: components["schemas"]["MajorCategoryInput"][];
      /**
       * Medium Categories
       * @default []
       */
      medium_categories: components["schemas"]["MediumCategoryInput"][];
    };
    /**
     * UpdateConditionStatusIntentInput
     * @description 更新する疾患状態の入力。
     */
    UpdateConditionStatusIntentInput: {
      /** Condition Name */
      condition_name: string;
      /** New Status */
      new_status: string;
      /** Is Contraindication Target */
      is_contraindication_target?: boolean | null;
    };
    /**
     * UpdateCorporatePolicyRequest
     * @description 法人ポリシー更新のリクエストモデル。
     */
    UpdateCorporatePolicyRequest: {
      require_prescription_audit: components["schemas"]["PolicySettingRequest"];
      prohibit_self_verification: components["schemas"]["PolicySettingRequest"];
    };
    /**
     * UpdateEventDefinitionRequest
     * @description 法人独自イベント種別の変更入力。
     */
    UpdateEventDefinitionRequest: {
      /** Name */
      name?: string | null;
      /** Is Active */
      is_active?: boolean | null;
    };
    /**
     * UpdateMedicationHistoryDraftRequest
     * @description 下書きの更新の入力。
     */
    UpdateMedicationHistoryDraftRequest: {
      soap?: components["schemas"]["SoapInput"] | null;
      profile_updates?: components["schemas"]["ProfileUpdateInput"] | null;
      /** Method */
      method?: string | null;
      handbook_status?: components["schemas"]["HandbookStatusInput"] | null;
      residual_drug?: components["schemas"]["ResidualDrugInput"] | null;
      /** Information Sheet Provided */
      information_sheet_provided?: boolean | null;
      /** Additional Notes */
      additional_notes?: components["schemas"]["CategorizedNoteInput"][] | null;
      /** Billing Additions */
      billing_additions?:
        components["schemas"]["BillingAdditionRequest"][] | null;
    };
    /**
     * UpdateStoreLicensesRequest
     * @description 店舗許認可更新の入力モデル。
     */
    UpdateStoreLicensesRequest: {
      pharmacy_license: components["schemas"]["PharmacyLicenseRequest"];
      narcotics_retailer_license?:
        components["schemas"]["NarcoticsRetailerLicenseRequest"] | null;
    };
    /**
     * UpdateStorePolicyRequest
     * @description 店舗ポリシー更新の入力モデル。
     */
    UpdateStorePolicyRequest: {
      /** Require Prescription Audit */
      require_prescription_audit?: boolean | null;
      /** Prohibit Self Verification */
      prohibit_self_verification?: boolean | null;
    };
    /**
     * UserPermissionDto
     * @description 本人へ付与された権限の種類と法人・店舗の範囲。
     */
    UserPermissionDto: {
      permission_type: components["schemas"]["UserPermissionType"];
      /** Corporate Id */
      corporate_id: string;
      /** Store Id */
      store_id: string | null;
    };
    /**
     * UserPermissionType
     * @description 本人へ範囲付きで付与する三種類のユーザー権限。
     * @enum {string}
     */
    UserPermissionType:
      "general_user" | "managing_pharmacist" | "corporate_admin";
    /**
     * VendorLoginRequest
     * @description 運営者のログイン入力。
     */
    VendorLoginRequest: {
      /** Email */
      email: string;
      /** Password */
      password: string;
    };
    /**
     * VerifyDispensingRequest
     * @description 鑑査の入力。
     */
    VerifyDispensingRequest: {
      /** Result */
      result: string;
      /** Notes */
      notes?: string | null;
    };
    /**
     * WeekdayBusinessHoursDto
     * @description 曜日1つ分の公開値。
     */
    WeekdayBusinessHoursDto: {
      /** Weekday */
      weekday: string;
      /** Slots */
      slots: components["schemas"]["BusinessHourSlotDto"][];
    };
    /**
     * WeekdayBusinessHoursInput
     * @description 曜日1つ分の開局予定。時間帯が空なら定休日。
     */
    WeekdayBusinessHoursInput: {
      weekday: components["schemas"]["BusinessWeekday"];
      /**
       * Slots
       * @default []
       */
      slots: components["schemas"]["BusinessHourSlotInput"][];
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  register_contract_contracts_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterContractRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredContract"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_user_corporates__corporate_id__users__membership_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        membership_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MembershipViewDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_membership_corporates__corporate_id__users__membership_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        membership_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeMembershipRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  suspend_account_accounts__account_id__suspension_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        account_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_me_me_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CurrentActorDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_my_stores_me_stores_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SelectableStoreDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_users_corporates__corporate_id__users_get: {
    parameters: {
      query?: {
        cursor?: string | null;
        limit?: number;
      };
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Page_MembershipViewDto_"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  suspend_membership_corporates__corporate_id__users__membership_id__suspension_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        membership_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  reactivate_membership_corporates__corporate_id__users__membership_id__reactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        membership_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_staff_for_admin_corporates__corporate_id__users__membership_id__staff_registration_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        membership_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterStaffForAdminRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_person_corporates__corporate_id__people_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterPersonRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  link_staff_person_corporates__corporate_id__staffs__staff_id__person_link_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LinkPersonRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  reactivate_account_accounts__account_id__reactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        account_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  login_auth_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LoginRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LoginSession"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  vendor_login_auth_vendor_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["VendorLoginRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LoginSession"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_password_auth_password_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangePasswordRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LoginSession"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  select_store_context_auth_store_context_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SelectStoreContextRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["LoginSession"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  logout_auth_logout_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  check_health_health_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ServiceStatusResponse"];
        };
      };
    };
  };
  list_corporates_corporates_get: {
    parameters: {
      query?: {
        name?: string | null;
        status?: string | null;
        cursor?: string | null;
        limit?: number;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CorporatePageDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_corporate_corporates_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterCorporateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_corporate_corporates__corporate_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CorporateResponseDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_corporate_name_corporates__corporate_id__name_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeCorporateNameRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_representative_corporates__corporate_id__representative_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeRepresentativeRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_corporate_status_corporates__corporate_id__status_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeCorporateStatusRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_corporate_policy_corporates__corporate_id__policy_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateCorporatePolicyRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_stores_corporates__corporate_id__stores_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreSummaryDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_store_corporates__corporate_id__stores_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterStoreRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_store_corporates__corporate_id__stores__store_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_store_names_corporates__corporate_id__stores__store_id__names_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreNamesRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_store_code_corporates__corporate_id__stores__store_id__code_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreCodeRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_store_address_corporates__corporate_id__stores__store_id__address_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreAddressRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_store_licenses_corporates__corporate_id__stores__store_id__licenses_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateStoreLicensesRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_store_policy_corporates__corporate_id__stores__store_id__policy_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateStorePolicyRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_effective_policy_corporates__corporate_id__stores__store_id__effective_policy_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EffectivePolicyDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_store_contact_info_corporates__corporate_id__stores__store_id__contact_info_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreContactInfoRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_insurance_pharmacy_number_corporates__corporate_id__stores__store_id__insurance_pharmacy_number_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeInsurancePharmacyNumberRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  suspend_store_corporates__corporate_id__stores__store_id__suspension_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreStatusRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  resume_store_corporates__corporate_id__stores__store_id__resumption_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreStatusRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  close_store_corporates__corporate_id__stores__store_id__closure_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreStatusRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  revoke_store_closure_corporates__corporate_id__stores__store_id__closure_revocation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStoreStatusRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_business_hours_corporates__corporate_id__stores__store_id__business_hours_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeBusinessHoursRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BusinessHoursDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_opening_status_corporates__corporate_id__stores__store_id__opening_status_get: {
    parameters: {
      query?: {
        /** @description 判定する日時。タイムゾーンが必要。省略時は現在。 */
        at?: string | null;
      };
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreOpeningStatusDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_status_history_corporates__corporate_id__stores__store_id__status_history_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StoreStatusChangeDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_managers_corporates__corporate_id__stores__store_id__manager_assignments_get: {
    parameters: {
      query?: {
        as_of?: string | null;
        cursor?: string | null;
        limit?: number;
      };
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Page_ManagerAssignmentDto_"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  manage_manager_corporates__corporate_id__stores__store_id__manager_assignments_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ManageManagerRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerAssignmentDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  end_manager_corporates__corporate_id__stores__store_id__manager_assignments__assignment_id__ending_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
        assignment_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EndManagerRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerAssignmentDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  cancel_manager_corporates__corporate_id__stores__store_id__manager_assignments__assignment_id__cancellation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
        assignment_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerAssignmentDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  replace_manager_corporates__corporate_id__stores__store_id__manager_replacement_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ReplaceManagerRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ManagerAssignmentDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_staffs_corporates__corporate_id__staffs_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StaffSummaryDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_staff_corporates__corporate_id__staffs_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterStaffRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BulkRegisteredStaffResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_staff_corporates__corporate_id__staffs__staff_id__get: {
    parameters: {
      query?: {
        /** @description 所属の判定に使う適用日。省略すると所属は空として扱う。 */
        target_date?: string | null;
      };
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json":
            | components["schemas"]["StaffDto"]
            | components["schemas"]["StaffSummaryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_staff_names_corporates__corporate_id__staffs__staff_id__names_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStaffNamesRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_staff_job_title_corporates__corporate_id__staffs__staff_id__job_title_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeStaffJobTitleRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_staff_qualifications_corporates__corporate_id__staffs__staff_id__qualifications_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["QualificationsRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  transfer_home_store_corporates__corporate_id__staffs__staff_id__home_store_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["TransferHomeStoreRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  assign_concurrent_store_corporates__corporate_id__staffs__staff_id__concurrent_stores_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AssignConcurrentStoreRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  remove_concurrent_store_corporates__corporate_id__staffs__staff_id__concurrent_stores__store_id__delete: {
    parameters: {
      query: {
        /** @description 兼務を終了する日。この日までは在籍とする。 */
        end_date: string;
      };
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  retire_staff_corporates__corporate_id__staffs__staff_id__retirement_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RetireStaffRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  reactivate_staff_corporates__corporate_id__staffs__staff_id__reactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        staff_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_patient_corporates__corporate_id__patients_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterPatientRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RegisteredIdResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_patient_corporates__corporate_id__patients__patient_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_patient_heading_corporates__corporate_id__patients__patient_id__heading_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientHeadingDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_patient_heading_corporates__corporate_id__patients__patient_id__heading_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangePatientHeadingRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientHeadingDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_patient_names_corporates__corporate_id__patients__patient_id__names_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangePatientNamesRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_patient_birth_date_corporates__corporate_id__patients__patient_id__birth_date_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangePatientBirthDateRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_patient_profile_corporates__corporate_id__patients__patient_id__profile_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangePatientProfileRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  deactivate_patient_corporates__corporate_id__patients__patient_id__deactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DeactivatePatientRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  reactivate_patient_corporates__corporate_id__patients__patient_id__reactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ReactivatePatientRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  merge_patients_corporates__corporate_id__patients__patient_id__merge_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["MergePatientsRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MergePatientsResultDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_external_identifiers_corporates__corporate_id__patients__patient_id__external_identifiers_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientExternalIdentifierDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_external_identifier_corporates__corporate_id__patients__patient_id__external_identifiers_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterExternalIdentifierRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientExternalIdentifierDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_external_identifier_corporates__corporate_id__patient_external_identifiers__identifier_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        identifier_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientExternalIdentifierDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  deactivate_external_identifier_corporates__corporate_id__patient_external_identifiers__identifier_id__deactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        identifier_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_coverages_corporates__corporate_id__patients__patient_id__coverages_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientCoverageDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_coverage_corporates__corporate_id__patients__patient_id__coverages_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterCoverageRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientCoverageDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_coverage_corporates__corporate_id__coverages__coverage_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        coverage_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientCoverageDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_coverage_period_corporates__corporate_id__coverages__coverage_id__period_patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        coverage_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangeCoveragePeriodRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientCoverageDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  deactivate_coverage_corporates__corporate_id__coverages__coverage_id__deactivation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        coverage_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DeactivateCoverageRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientCoverageDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  record_coverage_selection_corporates__corporate_id__coverage_selections_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecordCoverageSelectionRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CoverageSelectionRecordDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_last_coverage_selection_corporates__corporate_id__coverage_selections_latest_get: {
    parameters: {
      query: {
        /** @description 受付を行う店舗のID。 */
        store_id: string;
        /** @description 対象患者のID。 */
        patient_id: string;
        /** @description 資格の有効性を判定する業務日。 */
        applied_on: string;
      };
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json":
            components["schemas"]["LastCoverageSelectionCandidateDto"] | null;
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  associate_reception_medication_history_corporates__corporate_id__receptions__reception_id__medication_history_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        reception_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AssociateReceptionMedicationHistoryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AssociateReceptionMedicationHistoryResponse"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_prescription_corporates__corporate_id__prescriptions_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterPrescriptionRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PrescriptionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_prescription_corporates__corporate_id__prescriptions__prescription_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        prescription_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PrescriptionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  ready_for_dispensing_corporates__corporate_id__prescriptions__prescription_id__readiness_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        prescription_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PrescriptionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  cancel_prescription_corporates__corporate_id__prescriptions__prescription_id__cancellation_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        prescription_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PrescriptionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  start_inquiry_corporates__corporate_id__prescriptions__prescription_id__inquiries_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        prescription_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["StartInquiryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PrescriptionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  resolve_inquiry_corporates__corporate_id__prescriptions__prescription_id__inquiries__inquiry_number__resolution_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        prescription_id: string;
        inquiry_number: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ResolveInquiryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PrescriptionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  audit_drug_interactions_corporates__corporate_id__prescriptions_audit_interactions_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AuditDrugInteractionsRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DrugInteractionAuditReportDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  start_dispensing_corporates__corporate_id__dispensings_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["StartDispensingRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_dispensing_corporates__corporate_id__dispensings__dispensing_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        dispensing_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  record_dispensed_content_corporates__corporate_id__dispensings__dispensing_id__dispensed_content_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        dispensing_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecordDispensedContentRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  verify_dispensing_corporates__corporate_id__dispensings__dispensing_id__verification_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        dispensing_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["VerifyDispensingRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  record_audit_corporates__corporate_id__dispensings__dispensing_id__audit_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        dispensing_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecordAuditRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  complete_dispensing_corporates__corporate_id__dispensings__dispensing_id__completion_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        dispensing_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CompleteDispensingRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_dispensings_by_prescription_corporates__corporate_id__prescriptions__prescription_id__dispensings_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        prescription_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DispensingProcessDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  start_medication_history_corporates__corporate_id__medication_histories_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["StartMedicationHistoryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  start_event_medication_history_corporates__corporate_id__events__event_id__medication_history_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        event_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["StartEventMedicationHistoryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_medication_history_corporates__corporate_id__medication_histories__record_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_medication_history_view_corporates__corporate_id__medication_histories__record_id__view_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryViewDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_external_prescription_corrections_corporates__corporate_id__medication_history_external_corrections_get: {
    parameters: {
      query?: {
        store_id?: string | null;
        status?: ("pending" | "investigating" | "resolved") | null;
        cursor?: string | null;
        limit?: number;
      };
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["Page_PendingExternalCorrectionDto_"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  review_external_prescription_correction_corporates__corporate_id__medication_histories__record_id__external_corrections__correction_id__reviews_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
        correction_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ReviewExternalPrescriptionCorrectionRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_medication_history_draft_corporates__corporate_id__medication_histories__record_id__draft_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateMedicationHistoryDraftRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  finalize_medication_history_corporates__corporate_id__medication_histories__record_id__finalization_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody?: {
      content: {
        "application/json":
          components["schemas"]["FinalizeMedicationHistoryRequest"] | null;
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  amend_medication_history_corporates__corporate_id__medication_histories__record_id__amendments_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AmendMedicationHistoryRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  correct_medication_history_fact_corporates__corporate_id__medication_histories__record_id__corrections_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CorrectMedicationHistoryFactRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  add_follow_up_corporates__corporate_id__medication_histories__record_id__follow_ups_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AddFollowUpRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  record_tracing_report_corporates__corporate_id__medication_histories__record_id__tracing_reports_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecordTracingReportRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  record_tracing_report_response_corporates__corporate_id__medication_histories__record_id__tracing_reports__report_id__response_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
        report_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RecordTracingReportResponseRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  verify_statutory_record_corporates__corporate_id__medication_histories__record_id__statutory_record_sufficiency_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        record_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["StatutoryRecordSufficiencyDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_medication_histories_corporates__corporate_id__patients__patient_id__medication_histories_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicationHistoryDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_medical_profile_corporates__corporate_id__patients__patient_id__medical_profile_get: {
    parameters: {
      query: {
        /** @description 併用薬の継続判定に使う基準日。 */
        as_of: string;
      };
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientMedicalProfileDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  rebuild_medical_profile_corporates__corporate_id__patients__patient_id__medical_profile_rebuild_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RebuildMedicalProfileRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PatientMedicalProfileDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_medication_history_category_catalog_corporates__corporate_id__medication_history_category_catalog_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CategoryCatalogDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_medication_history_category_catalog_corporates__corporate_id__medication_history_category_catalog_put: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateCategoryCatalogRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CategoryCatalogDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_event_definitions_corporates__corporate_id__event_definitions_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventDefinitionDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  create_event_definition_corporates__corporate_id__event_definitions_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateEventDefinitionRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventDefinitionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_event_definition_corporates__corporate_id__event_definitions__event_type_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        event_type_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateEventDefinitionRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventDefinitionDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  create_event_corporates__corporate_id__events_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateEventRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_event_corporates__corporate_id__events__event_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        event_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EventDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_related_event_candidates_corporates__corporate_id__patients__patient_id__events_related_candidates_get: {
    parameters: {
      query: {
        store_id: string;
      };
      header?: never;
      path: {
        corporate_id: string;
        patient_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["RelatedEventCandidateDto"][];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  register_medicine_medicines_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RegisterMedicineRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicineDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_effective_medicine_medicines__code_type___code__get: {
    parameters: {
      query: {
        /** @description 収載期間の判定に使う時点。処方箋の判定では交付日を渡す。 */
        as_of: string;
      };
      header?: never;
      path: {
        code_type: string;
        code: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MedicineDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  import_yj_catalog_medicines_import_csv_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ImportYjCatalogRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportYjCatalogResultDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  ingest_nsips_corporates__corporate_id__stores__store_id__integrations_nsips_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        corporate_id: string;
        store_id: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["IngestNsipsRequest"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["IngestNsipsResultDto"];
        };
      };
      /** @description 資格情報が無い、または検証できない。 */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 主体は判明したが、その操作の権限が無い。 */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 対象が存在しない、または他テナントのため隠されている。 */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 一意制約違反や楽観ロック衝突など、既存の状態と衝突する。 */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description 入力値が形式またはドメイン規則を満たさない。 */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
}
