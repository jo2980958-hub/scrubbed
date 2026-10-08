import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './auth/AuthContext';
import { ToastProvider } from './components/ui';
import Shell from './components/Shell';
import Login from './pages/Login';
import CaseBoard from './pages/CaseBoard';
import CaseDetail from './pages/CaseDetail';
import Followups from './pages/Followups';
import StaffPage from './pages/Staff';
import { ApiError } from './api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          {/* HashRouter: deep links work on S3/CloudFront without rewrite rules. */}
          <HashRouter>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<Shell />}>
                <Route index element={<CaseBoard />} />
                <Route path="cases/:id" element={<CaseDetail />} />
                <Route path="followups" element={<Followups />} />
                <Route path="staff" element={<StaffPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </HashRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
