/**
 * Forgot Password Page Module
 * Router-compatible module that renders the Svelte forgot password page
 */

import { mount } from "svelte";
import ForgotPasswordPage from "./lib/components/auth/ForgotPasswordPage.svelte";

export default async function initForgotPasswordPage() {
  const app = document.getElementById("app");
  app.innerHTML = "";
  mount(ForgotPasswordPage, { target: app });
}
