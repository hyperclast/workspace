/**
 * Password Reset Page Module
 * Router-compatible module that renders the Svelte reset password page
 */

import { mount } from "svelte";
import ResetPasswordPage from "./lib/components/auth/ResetPasswordPage.svelte";

export default function initResetPasswordPage() {
  const app = document.getElementById("app");
  app.innerHTML = "";
  mount(ResetPasswordPage, { target: app });
}
