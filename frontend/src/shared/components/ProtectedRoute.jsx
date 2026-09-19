import { Navigate, Outlet, useLocation } from "react-router-dom";

import { isLoggedIn } from "../services/tokenStorage.js";

function ProtectedRoute() {
  const location = useLocation();

  if (!isLoggedIn()) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
