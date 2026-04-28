import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import SetupPage from './pages/Setup';
import DeploymentsPage from './pages/Deployments';
import DeploymentDetailPage from './pages/DeploymentDetail';
import NewDeploymentPage from './pages/NewDeployment';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate replace to="/setup" />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/deployments" element={<DeploymentsPage />} />
        <Route path="/deployments/new" element={<NewDeploymentPage />} />
        <Route path="/deployments/:deploymentId" element={<DeploymentDetailPage />} />
      </Routes>
    </Layout>
  );
}
