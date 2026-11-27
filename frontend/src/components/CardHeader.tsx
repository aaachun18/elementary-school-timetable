import type { ReactElement, ReactNode } from "react";
import InfoPopover from "./InfoPopover";
import { CARD_HEADER, CARD_TITLE } from "../styles/ui";

// Task 98 Phase C: a card's one title, with an (i) holding its
// explanation next to it.
export default function CardHeader({
  title,
  info,
  children,
}: {
  title: string;
  info?: ReactNode;
  // Anything else on the title row (a count, a badge).
  children?: ReactNode;
}): ReactElement {
  return (
    <div className={CARD_HEADER}>
      <h2 className={CARD_TITLE}>{title}</h2>
      {info !== undefined && <InfoPopover label={`關於${title}`}>{info}</InfoPopover>}
      {children}
    </div>
  );
}
