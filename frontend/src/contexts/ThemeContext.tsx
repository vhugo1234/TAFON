import React, {
  createContext,
  useContext,
  useMemo,
  useState,
  ReactNode,
  useEffect,
} from "react";
import { ThemeProvider, createTheme, Theme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import GlobalStyles from "@mui/material/GlobalStyles";
import baseTheme from "../theme";
import {
  redDarkTheme,
  solarizedDarkTheme,
  greenForestTheme,
  oceanBlueTheme,
  purpleNightTheme,
} from "../themes";

/**
 * ThemeProviderWrapper atualizado para garantir que:
 * - CssBaseline Ã© aplicado dentro do ThemeProvider (assim o body recebe o background do tema)
 * - GlobalStyles ajusta body background/color a partir do tema (garante cobertura completa)
 * - 'dark' mode tem backgrounds explÃ­citos para ficar realmente escuro
 * - mantÃ©m compatibilidade com API antiga (theme / setTheme)
 */

type ThemeContextType = {
  theme: string;
  setTheme: (k: string) => void;
  themeKey: string;
  setThemeKey: (k: string) => void;
};

const ThemeContext = createContext<ThemeContextType>({
  theme: "light",
  setTheme: () => {},
  themeKey: "light",
  setThemeKey: () => {},
});

export function useThemeContext() {
  return useContext(ThemeContext);
}

const customThemes: Record<string, any> = {
  "red-dark": redDarkTheme,
  "solarized-dark": solarizedDarkTheme,
  "green-forest": greenForestTheme,
  "ocean-blue": oceanBlueTheme,
  "purple-night": purpleNightTheme,
  // explicit dark baseline so MUI components and backgrounds turn dark
  dark: {
    palette: {
      mode: "dark",
      background: {
        default: "#0b0b0f", // app background
        paper: "#121216",   // surfaces / Paper
      },
      text: {
        primary: "#e6e6e9",
        secondary: "#bfbfc4",
      },
      divider: "rgba(255,255,255,0.08)",
    },
  },
  light: {
    palette: {
      mode: "light",
      background: {
        default: "#f6f9fb",
        paper: "#ffffff",
      },
      text: {
        primary: "#111827",
        secondary: "#6b7280",
      },
      divider: "rgba(0,0,0,0.08)",
    },
  },
};

function getSystemPrefKey() {
  if (typeof window === "undefined" || !window.matchMedia) return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProviderWrapper({ children }: { children: ReactNode }) {
  const [themeKey, setThemeKey] = useState<string>(() => {
    try {
      return localStorage.getItem("app_theme") || "light";
    } catch {
      return "light";
    }
  });

  // Expose legacy-friendly API used elsewhere (theme / setTheme)
  const theme = themeKey;
  const setTheme = (k: string) => setThemeKey(k);

  const effectiveKey = useMemo(() => {
    if (themeKey === "system") return getSystemPrefKey();
    return themeKey;
  }, [themeKey]);

  useEffect(() => {
    if (themeKey !== "system" || typeof window === "undefined" || !window.matchMedia) {
      return;
    }
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setThemeKey((k) => (k === "system" ? "system" : k));
    mq.addEventListener ? mq.addEventListener("change", handler) : mq.addListener(handler);
    return () =>
      mq.removeEventListener ? mq.removeEventListener("change", handler) : mq.removeListener(handler);
  }, [themeKey]);

  // Build MUI Theme by merging baseTheme with the chosen custom options
  const muiTheme: Theme = useMemo(() => {
    const overrides = customThemes[effectiveKey] ?? customThemes["light"];
    // createTheme merges and ensures the palette.mode is honored by MUI
    return createTheme(baseTheme, overrides);
  }, [effectiveKey]);

  useEffect(() => {
    try {
      localStorage.setItem("app_theme", themeKey);
    } catch {}
  }, [themeKey]);

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        themeKey,
        setThemeKey,
      }}
    >
      <ThemeProvider theme={muiTheme}>
        {/* CssBaseline inside ThemeProvider ensures MUI global styles apply per-theme */}
        <CssBaseline />
        {/* Force body background and color to match theme (covers non-MUI elements) */}
        <GlobalStyles
          styles={(theme) => ({
            body: {
              backgroundColor: (theme as Theme).palette.background.default,
              color: (theme as Theme).palette.text.primary,
              transition: "background-color 200ms ease, color 200ms ease",
            },
            // Optional: ensure html height = 100% so background covers full page
            html: { height: "100%" },
            "#root": { minHeight: "100vh" },
          })}
        />
        {children}
      </ThemeProvider>
    </ThemeContext.Provider>
  );
}

