/**
 * Signup Page Module
 * Router-compatible module that renders the Svelte signup page
 */

import { mount } from "svelte";
import SignupPage from "./lib/components/auth/SignupPage.svelte";

export default async function initSignupPage() {
  const app = document.getElementById("app");
  app.innerHTML = "";
  mount(SignupPage, { target: app });
}
