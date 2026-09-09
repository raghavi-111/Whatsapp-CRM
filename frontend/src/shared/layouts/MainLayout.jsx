import { Outlet } from "react-router-dom";

function MainLayout() {
  return (
    <main className="app-shell">
      <Outlet />
    </main>
  );
}

export default MainLayout;
