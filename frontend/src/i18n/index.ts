import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { resources } from "./messages";

void i18n.use(initReactI18next).init({
  resources,
  lng: "zh",
  fallbackLng: "zh",
  supportedLngs: ["zh", "en"],
  interpolation: {
    escapeValue: false,
  },
  returnNull: false,
});

export default i18n;
