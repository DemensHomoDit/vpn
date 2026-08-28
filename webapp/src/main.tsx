import React from "react";
import ReactDOM from "react-dom/client";
import WebApp from "@twa-dev/sdk";
import App from "./App";
import "./styles.css";

const applyTheme = () => {
  const scheme = WebApp.colorScheme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = scheme;
  const bg = scheme === "light" ? "#f2f2f7" : "#000000";
  try {
    WebApp.setHeaderColor(bg);
    WebApp.setBackgroundColor(bg);
  } catch {
    /* не все клиенты поддерживают */
  }
};

WebApp.ready();
WebApp.expand();
applyTheme();
WebApp.onEvent("themeChanged", applyTheme);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
