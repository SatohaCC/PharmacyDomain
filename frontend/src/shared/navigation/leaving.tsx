import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
const LeaveContext = createContext<{
  register: (message: string) => () => void;
  allow: () => boolean;
}>({ register: () => () => {}, allow: () => true });
export function LeaveProvider({ children }: { children: ReactNode }) {
  const warning = useRef<string | undefined>(undefined);
  const value = {
    register: (message: string) => {
      warning.current = message;
      return () => {
        warning.current = undefined;
      };
    },
    allow: () => !warning.current || window.confirm(warning.current),
  };
  return (
    <LeaveContext.Provider value={value}>{children}</LeaveContext.Provider>
  );
}
export function useLeaveWarning(enabled: boolean, message: string) {
  const { register } = useContext(LeaveContext);
  useEffect(() => {
    if (enabled) return register(message);
  }, [enabled, message, register]);
}
export function useAllowLeave() {
  return useContext(LeaveContext).allow;
}
