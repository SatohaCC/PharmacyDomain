import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
} from "oidc-client-ts";
import { endLocalSession } from "./local-authentication";

const SESSION_STORAGE_KEY = "pharmacydomain_access_token";

let token = "";

export const accessToken = () => {
  if (token) return token;
  if (typeof window !== "undefined" && window.sessionStorage) {
    const saved = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (saved) {
      token = saved;
      return token;
    }
  }
  return "";
};

export const setAccessToken = (value: string) => {
  token = value;
  if (typeof window !== "undefined" && window.sessionStorage) {
    if (value) {
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, value);
    } else {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }
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
  try {
    await endLocalSession();
  } finally {
    setAccessToken("");
    location.assign("/login");
  }
}
