// Swatch colours for the colour names used in the catalogue.
const SWATCHES: Record<string, string> = {
  "navy blue": "#1d2b4f",
  navy: "#1d2b4f",
  white: "#ffffff",
  ivory: "#f6f1e3",
  cream: "#f1e8d4",
  "heather gray": "#b9bcc2",
  "light gray": "#d5d8dd",
  gray: "#9aa0a8",
  "dark heather gray": "#6b7079",
  "charcoal gray": "#4a4e56",
  "heather charcoal gray": "#55595f",
  "dark heather charcoal": "#43464c",
  black: "#111214",
  red: "#c8102e",
  "dusty coral": "#e4927d",
  blue: "#2a62d8",
  "royal blue": "#2448c9",
  "light blue": "#8fc1ec",
  yellow: "#f2c230",
  gold: "#c9a227",
  green: "#2e8b57",
  multicolor: "conic-gradient(#c8102e, #f2c230, #2e8b57, #2a62d8, #c8102e)",
};

export const swatch = (name: string) => SWATCHES[name.toLowerCase()] ?? "#c9ced6";
