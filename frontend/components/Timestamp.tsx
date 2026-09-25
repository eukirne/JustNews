"use client";

import { useEffect, useState } from "react";
import { formatAbsolute, formatRelative } from "@/lib/formatDate";

export function Timestamp({ publishedAt, className }: { publishedAt: string; className?: string }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  return (
    <time dateTime={publishedAt} title={formatAbsolute(publishedAt)} className={className}>
      {formatRelative(publishedAt, now)}
    </time>
  );
}
