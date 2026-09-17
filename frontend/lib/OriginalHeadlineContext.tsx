"use client";

import { createContext, useContext, useState } from "react";

const OriginalHeadlineContext = createContext<{
  show: boolean;
  toggle: () => void;
}>({ show: false, toggle: () => {} });

export function OriginalHeadlineProvider({ children }: { children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <OriginalHeadlineContext.Provider value={{ show, toggle: () => setShow((s) => !s) }}>
      {children}
    </OriginalHeadlineContext.Provider>
  );
}

export function useOriginalHeadline() {
  return useContext(OriginalHeadlineContext);
}
