import React from "react";
import ReactDOM from "react-dom/client";
import WebApp from "@twa-dev/sdk";
import App from "./App";
import "./styles.css";

WebApp.ready();
WebApp.expand();
WebApp.setHeaderColor("#0b1020");
WebApp.setBackgroundColor("#0b1020");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);