import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...nextVitals,
  {
    rules: {
      // These effects intentionally sync React state with external systems
      // (localStorage portfolio store, lightweight-charts data, mount flags)
      // and mutate ref-held chart data buffers for live updates.
      // The new react-hooks heuristics flag them as false positives here.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/immutability": "off",
    },
  },
];

export default config;
