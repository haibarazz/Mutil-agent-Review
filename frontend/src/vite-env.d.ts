/// <reference types="vite/client" />

import type { DetailedHTMLProps, HTMLAttributes } from "react";

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "agent-px": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        id?: string;
        size?: string;
        "no-bg"?: boolean;
      };
    }
  }
}
