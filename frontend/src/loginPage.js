/**
 * Login Page Module
 * Router-compatible module that renders the Svelte login page
 */

import { mount } from "svelte";
import LoginPage from "./lib/components/auth/LoginPage.svelte";

export default async function initLoginPage() {
  const app = document.getElementById("app");
  app.innerHTML = "";
  mount(LoginPage, { target: app });
}
