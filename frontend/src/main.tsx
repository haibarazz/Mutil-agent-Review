import React from "react";
import { createRoot } from "react-dom/client";

import "./styles/tokens.css";
import "./styles/workbench.css";
import "./styles/review-theater.css";
import { WorkbenchHome } from "./pages/WorkbenchHome";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WorkbenchHome />
  </React.StrictMode>,
);
