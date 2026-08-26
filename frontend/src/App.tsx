import OpsCenterPage from "./pages/OpsCenterPage";
import StorePage from "./pages/StorePage";
import "./ops.css";

export default function App() {
  return window.location.pathname.startsWith("/ops")
    ? <OpsCenterPage />
    : <StorePage />;
}
