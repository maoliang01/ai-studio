"use client";

import { useState } from "react";
import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DateRangeValue, DateRangePreset } from "@/types";

type PresetOption = "today" | "week" | "month" | "custom";

interface DateRangeSelectorProps {
  value?: DateRangeValue;
  onChange: (value: DateRangeValue | undefined) => void;
  disabled?: boolean;
}

export function DateRangeSelector({
  value,
  onChange,
  disabled = false,
}: DateRangeSelectorProps) {
  const [selectedPreset, setSelectedPreset] = useState<PresetOption | null>(
    value?.preset || null
  );
  const [startDate, setStartDate] = useState(value?.custom?.startDate || "");
  const [endDate, setEndDate] = useState(value?.custom?.endDate || "");

  const presets: { key: PresetOption; label: string }[] = [
    { key: "today", label: "近一日" },
    { key: "week", label: "近一周" },
    { key: "month", label: "近一月" },
    { key: "custom", label: "自定义" },
  ];

  const handlePresetChange = (key: PresetOption) => {
    setSelectedPreset(key);

    if (key === "custom") {
      onChange({
        custom: { startDate, endDate },
      });
    } else {
      onChange({ preset: key as DateRangePreset });
    }
  };

  const handleDateChange = () => {
    onChange({
      custom: { startDate, endDate },
    });
  };

  const clearDateRange = () => {
    setSelectedPreset(null);
    setStartDate("");
    setEndDate("");
    onChange(undefined);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          时间范围
        </label>
        {selectedPreset && (
          <button
            onClick={clearDateRange}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            disabled={disabled}
          >
            清除筛选
          </button>
        )}
      </div>

      {/* 预设选项 */}
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <button
            key={p.key}
            onClick={() => handlePresetChange(p.key)}
            disabled={disabled}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
              selectedPreset === p.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground",
              disabled && "opacity-50 cursor-not-allowed"
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* 自定义日期选择 */}
      {selectedPreset === "custom" && (
        <div className="flex items-center gap-3 pt-2 animate-in fade-in duration-200">
          <div className="flex items-center gap-2 flex-1">
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                handleDateChange();
              }}
              disabled={disabled}
              className={cn(
                "flex-1 px-3 py-1.5 text-sm border rounded-md",
                "bg-background focus:outline-none focus:ring-2 focus:ring-ring",
                disabled && "opacity-50 cursor-not-allowed"
              )}
              placeholder="起始日期"
            />
            <span className="text-muted-foreground text-sm">至</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                handleDateChange();
              }}
              disabled={disabled}
              className={cn(
                "flex-1 px-3 py-1.5 text-sm border rounded-md",
                "bg-background focus:outline-none focus:ring-2 focus:ring-ring",
                disabled && "opacity-50 cursor-not-allowed"
              )}
              placeholder="结束日期"
            />
          </div>
        </div>
      )}

      {/* 提示信息 */}
      {selectedPreset && selectedPreset !== "custom" && (
        <p className="text-xs text-muted-foreground">
          将筛选出{" "}
          {selectedPreset === "today"
            ? "今天"
            : selectedPreset === "week"
              ? "近一周内"
              : "近一月内"}{" "}
          发布的文章
        </p>
      )}
    </div>
  );
}