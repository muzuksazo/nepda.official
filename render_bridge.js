// Connect the web editor to the Blender companion on the user's own PC.
// The page stays open; passwords are sent in headers, never in URLs.
(() => {
"use strict";
const local = !!window.HOOKCUT_LOCAL;
const base = local ? "" : "http://localhost:8000";
const key = "hookcut_render_pw";
let password = "";
const help = "내 PC 렌더 서버에 연결하지 못했어요. '훅컷 실행.bat'을 켜고, 브라우저가 요청하면 로컬 네트워크 접근을 허용해 주세요.";
function readPassword(again = false) {
  if (!again && !password) {
    try { password = sessionStorage.getItem(key) || sessionStorage.getItem("hookcut_pw") || ""; } catch (e) {}
  }
  if (!password || again) password = window.prompt(again ? "렌더 서버 비밀번호가 맞지 않아요. 다시 입력해 주세요." : "블렌더 렌더 비밀번호를 입력해 주세요.") || "";
  if (!password) throw new Error("렌더 비밀번호를 입력해야 블렌더를 연결할 수 있어요.");
  try { sessionStorage.setItem(key, password); } catch (e) {}
  return password;
}
async function request(path, init = {}, retry = true) {
  if (!/^\/api\/(render|status|preview|video)(\?|$)/.test(path)) throw new Error("허용되지 않은 렌더 요청이에요.");
  const headers = new Headers(init.headers);
  if (!local) headers.set("X-Hookcut-Password", readPassword());
  let response;
  try {
    response = await fetch(base + path, { ...init, headers, cache: "no-store", credentials: local ? "same-origin" : "omit",
      targetAddressSpace: "loopback", signal: init.signal || AbortSignal.timeout(init.method === "POST" || path.startsWith("/api/video") ? 120000 : 15000) });
  } catch (e) { throw new Error(help); }
  if (!local && response.status === 401 && retry) {
    readPassword(true);
    return request(path, init, false);
  }
  return response;
}
async function connect() {
  if (!local && navigator.permissions?.query) {
    let permission;
    try { permission = await navigator.permissions.query({ name: "loopback-network" }); } catch (e) {}
    if (permission?.state === "denied") throw new Error("브라우저에서 이 사이트의 '로컬 네트워크' 또는 '루프백 네트워크' 권한을 허용한 뒤 다시 눌러 주세요.");
  }
  let response;
  try {
    response = await fetch(base + "/api/ping", { cache: "no-store", credentials: local ? "same-origin" : "omit",
      targetAddressSpace: "loopback", signal: AbortSignal.timeout(15000) });
  } catch (e) { throw new Error(help); }
  const status = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(status.error || help);
  if (!local && !(status.bridge >= 2)) throw new Error("렌더 서버를 다시 실행해야 해요. '훅컷 실행.bat' 창을 닫고 다시 켜 주세요.");
  if (!status.blender) throw new Error("이 PC에서 Blender를 찾지 못했어요. Blender 설치와 렌더 서버 설정을 확인해 주세요.");
  return status;
}
window.HookCutRender = { connect, request };
})();
