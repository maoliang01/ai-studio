"use client";
import { ChevronUp, ChevronDown, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  entityName: string;
  total: number;
  current: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}

export default function HighlightOverlay({ entityName, total, current, onPrev, onNext, onClose }: Props) {
  if (total === 0) {
    return (
      <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-amber-100 border border-amber-300 text-amber-800 text-sm px-4 py-2 rounded-md shadow-md flex items-center gap-2">
        <span>未在文中找到 "{entityName}"</span>
        <Button size="icon" variant="ghost" onClick={onClose} className="h-5 w-5"><X className="h-3 w-3" /></Button>
      </div>
    );
  }
  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-yellow-100 border border-yellow-300 text-yellow-900 text-sm px-3 py-1.5 rounded-md shadow-md flex items-center gap-2">
      <span className="font-medium">{entityName}</span>
      <span className="text-yellow-700">·</span>
      <span>第 {current} / {total} 处</span>
      <Button size="icon" variant="ghost" onClick={onPrev} disabled={current <= 1} className="h-6 w-6" title="上一处"><ChevronUp className="h-3.5 w-3.5" /></Button>
      <Button size="icon" variant="ghost" onClick={onNext} disabled={current >= total} className="h-6 w-6" title="下一处"><ChevronDown className="h-3.5 w-3.5" /></Button>
      <Button size="icon" variant="ghost" onClick={onClose} className="h-6 w-6" title="关闭"><X className="h-3.5 w-3.5" /></Button>
    </div>
  );
}
