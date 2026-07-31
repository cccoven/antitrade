export const automationsUi = {
  buttonStyle: { fontSize: "var(--font-ui)", fontWeight: 400 },
  inputStyle: { fontSize: "var(--font-ui)" },
} as const;

export const automationTimezones: readonly string[] = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Asia/Dubai",
  "Asia/Shanghai",
  "Asia/Hong_Kong",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
];
