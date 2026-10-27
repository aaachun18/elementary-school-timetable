import type { ReactElement, ReactNode } from "react";
import InfoPopover from "./InfoPopover";
import { PAGE_HEADER, PAGE_HEADER_ACTIONS, PAGE_HEADER_MAIN, PAGE_HEADER_TITLE } from "../styles/ui";

// Task 98 Phase C: a page's one header row -- the title, small tags beside
// it (學期 · 紀錄 #N, a status badge), an (i) holding the page's
// explanation, and the page's actions on the right.
export default function PageHeader({
  title,
  meta,
  info,
  infoLabel,
  actions,
}: {
  title: ReactNode;
  meta?: ReactNode;
  info?: ReactNode;
  // The (i) button's accessible name; defaults to 「關於…」 + the title.
  infoLabel?: string;
  actions?: ReactNode;
}): ReactElement {
  return (
    <div className={PAGE_HEADER}>
      <div className={PAGE_HEADER_MAIN}>
        <h1 className={PAGE_HEADER_TITLE}>{title}</h1>
        {info !== undefined && (
          <InfoPopover label={infoLabel ?? `關於${typeof title === "string" ? title : "這一頁"}`}>{info}</InfoPopover>
        )}
        {meta}
      </div>
      {actions !== undefined && <div className={PAGE_HEADER_ACTIONS}>{actions}</div>}
    </div>
  );
}
