import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ParentChildCommunication from "../parent_child_communication";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ParentChildCommunication />
  </StrictMode>,
);
