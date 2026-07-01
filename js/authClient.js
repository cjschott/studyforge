import { apiGet, apiPost, setBackendUser } from "./api.js";

export async function fetchCurrentUser() {
  const user = await apiGet("/api/auth/me");
  setBackendUser(user);
  return user;
}

export async function login(username, password) {
  const response = await apiPost("/api/auth/login", { username, password });
  setBackendUser(response.user);
  return response.user;
}

export async function logout() {
  await apiPost("/api/auth/logout", {});
  setBackendUser(null);
}

export function renderLoginView(root, onSubmit) {
  root.innerHTML = `
    <section class="login-panel">
      <div>
        <h2>Sign In</h2>
        <p class="muted">The StudyForge backend is available. Sign in to use DB-backed courses and cross-device progress.</p>
      </div>
      <form id="login-form" class="card login-card">
        <div class="field">
          <label for="login-username">Username</label>
          <input id="login-username" class="input" name="username" autocomplete="username" required>
        </div>
        <div class="field">
          <label for="login-password">Password</label>
          <input id="login-password" class="input" name="password" type="password" autocomplete="current-password" required>
        </div>
        <button class="button button-primary" type="submit">Log In</button>
        <p id="login-error" class="helper-text error-text" hidden></p>
      </form>
    </section>
  `;

  root.querySelector("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const error = root.querySelector("#login-error");
    const data = new FormData(form);
    error.hidden = true;
    try {
      await onSubmit(String(data.get("username") || ""), String(data.get("password") || ""));
    } catch (loginError) {
      error.textContent = loginError.message;
      error.hidden = false;
    }
  });
}
