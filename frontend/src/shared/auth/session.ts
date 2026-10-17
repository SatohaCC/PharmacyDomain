import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
} from "oidc-client-ts";
let token = "";
export const accessToken = () => token;
export const setAccessToken = (value: string) => {
  token = value;
};
let manager: UserManager | undefined;
export function oidc(): UserManager | undefined {
  const authority = import.meta.env.VITE_OIDC_AUTHORITY;
  const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;
  if (!authority || !clientId) return undefined;
  return (manager ??= new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: location.origin + "/auth/callback",
    post_logout_redirect_uri: location.origin + "/login",
    response_type: "code",
    scope: import.meta.env.VITE_OIDC_SCOPE || "openid profile",
    automaticSilentRenew: false,
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    stateStore: new WebStorageStateStore({ store: sessionStorage }),
  }));
}
export async function login(returnTo: string) {
  const manager = oidc();
  if (!manager) throw new Error("OIDC接続先が未設定です。");
  await manager.signinRedirect({ state: { returnTo } });
}
export async function logout() {
  token = "";
  const manager = oidc();
  if (manager) {
    await manager.signoutRedirect();
  } else location.assign("/login");
}
