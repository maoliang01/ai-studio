"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

type ProgressProps = React.ComponentProps<"div"> & {
  value?: number
}

function Progress({ className, value = 0, ...props }: ProgressProps) {
  const clampedValue = Math.min(100, Math.max(0, value))

  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clampedValue}
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-primary/20",
        className
      )}
      {...props}
    >
      <div
        data-slot="progress-indicator"
        className="h-full w-full flex-1 bg-primary transition-all"
        style={{ transform: `translateX(-${100 - clampedValue}%)` }}
      />
    </div>
  )
}

export { Progress }
