import { Sidebar, MobileSidebar } from "@/components/Sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen" style={{ background: "var(--cf-bg)" }}>
      <Sidebar />
      <MobileSidebar />
      <main className="flex-1 md:ml-[220px] p-6 overflow-y-auto" style={{ minHeight: "100vh" }}>
        {children}
      </main>
    </div>
  );
}
