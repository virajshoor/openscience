import React from "react";
import ReactDOM from "react-dom/client";
import { MantineProvider, createTheme } from "@mantine/core";
import App from "./App";
import "./styles.css";

const theme = createTheme({
  primaryColor: "teal",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif",
  fontFamilyMonospace: "'JetBrains Mono', 'SF Mono', Menlo, monospace",
  defaultRadius: 6,
  headings: { fontWeight: "600" },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <App />
    </MantineProvider>
  </React.StrictMode>
);