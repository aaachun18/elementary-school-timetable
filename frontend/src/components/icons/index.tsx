import type { ReactElement, ReactNode } from "react";

// Task 98: the project's own inline SVG icons -- no icon package. Every
// icon is a 24×24 viewBox outline drawn with currentColor at stroke 1.75,
// so it takes the color of the text / button around it. Decorative by
// default (aria-hidden): the button or link carrying it has the accessible
// name.

export const ICON_SIZE = 20;

interface IconProps {
  size?: number;
  className?: string;
}

function SvgIcon({ size = ICON_SIZE, className, children }: IconProps & { children: ReactNode }): ReactElement {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {children}
    </svg>
  );
}

// (i) -- InfoPopover's trigger.
export function InfoIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <path d="M12 7.5h.01" />
    </SvgIcon>
  );
}

export function TrashIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M4 7h16" />
      <path d="M9 7V4.5h6V7" />
      <path d="M6 7l1 12.5h10L18 7" />
      <path d="M10 11v5" />
      <path d="M14 11v5" />
    </SvgIcon>
  );
}

export function CheckIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </SvgIcon>
  );
}

// Task 100: a row's 「編輯」 (EditIconButton) and 時段's 編輯 mode button.
export function PencilIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M4 20l1-4.5L15.5 5a2.1 2.1 0 013 3L8 18.5z" />
      <path d="M13.5 7l3 3" />
    </SvgIcon>
  );
}

// Task 100: CheckStatusTag's 「N 個錯誤」 / 「N 個警告」 (a triangle with !).
export function AlertIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M12 4l9 16H3z" />
      <path d="M12 10v4.5" />
      <path d="M12 17.5h.01" />
    </SvgIcon>
  );
}

// Home page cards: 開始排課 (a calendar with a plus).
export function CalendarPlusIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <rect x="3.5" y="5" width="17" height="15" rx="2" />
      <path d="M3.5 9.5h17" />
      <path d="M8 3v4" />
      <path d="M16 3v4" />
      <path d="M12 12.5v5" />
      <path d="M9.5 15h5" />
    </SvgIcon>
  );
}

// 排課紀錄 (a clipboard with lines).
export function ClipboardListIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <rect x="5" y="4.5" width="14" height="16" rx="2" />
      <path d="M9 3h6v3H9z" />
      <path d="M9 11h6" />
      <path d="M9 15h6" />
    </SvgIcon>
  );
}

// 學校資料 (a school building).
export function SchoolIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M3 10l9-6 9 6" />
      <path d="M5 9v11h14V9" />
      <path d="M10 20v-5h4v5" />
      <path d="M3 20h18" />
    </SvgIcon>
  );
}

// Login's 顯示密碼 / 隱藏密碼 toggle.
export function EyeIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </SvgIcon>
  );
}

export function EyeOffIcon(props: IconProps): ReactElement {
  return (
    <SvgIcon {...props}>
      <path d="M10.6 5.6A9.9 9.9 0 0112 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 01-2.8 3.6" />
      <path d="M6.4 6.9C3.9 8.6 2.5 12 2.5 12S6 18.5 12 18.5a9.6 9.6 0 004.6-1.2" />
      <path d="M9.9 9.9a3 3 0 004.2 4.2" />
      <path d="M3 3l18 18" />
    </SvgIcon>
  );
}
