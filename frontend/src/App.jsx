import AppRoutes from "./routes/AppRoutes.jsx";
import { NotificationProvider } from "./shared/components/NotificationProvider.jsx";

function App() {
  return (
    <NotificationProvider>
      <AppRoutes />
    </NotificationProvider>
  );
}

export default App;
