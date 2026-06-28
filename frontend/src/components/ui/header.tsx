import { cn } from "@/lib/utils";

interface HeaderProps {
  children: React.ReactNode;
  className?: string;
}

export function Header({ children, className }: HeaderProps) {
  return (
    <header
      className={cn(
        "flex h-14 items-center justify-between border-b border-border px-4",
        className
      )}
    >
      {children}
    </header>
  );
}

export function HeaderLeft({
  children,
  className,
}: HeaderProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {children}
    </div>
  );
}

export function HeaderRight({
  children,
  className,
}: HeaderProps) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      {children}
    </div>
  );
}