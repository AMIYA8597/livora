import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...nextVitals,
  {
    rules: {
      "@next/next/no-img-element": "off",
      // Data fetching goes through hooks/useApiQuery (no synchronous setState in effects), so
      // these hold as errors; a new warning would otherwise slip through CI unnoticed.
      "react-hooks/exhaustive-deps": "error",
      "react-hooks/set-state-in-effect": "error",
    },
  },
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts", "tsconfig.tsbuildinfo"],
  },
];

export default config;
