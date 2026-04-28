import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ApiDeployment } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import { useApi } from '../hooks/useApi';

function toDeploymentList(input: unknown): ApiDeployment[] {
  if (Array.isArray(input)) {
    return input as ApiDeployment[];
  }
  if (input && typeof input === 'object') {
    const maybeItems = (input as { items?: unknown }).items;
    if (Array.isArray(maybeItems)) {
      return maybeItems as ApiDeployment[];
    }
  }
  return [];
}

export default function DeploymentsPage() {
  const api = useApi();
  const [deployments, setDeployments] = useState<ApiDeployment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  async function refreshList() {
    setLoading(true);
    setError('');
    try {
      const result = await api.listDeployments();
      setDeployments(toDeploymentList(result));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load deployments');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshList();
  }, []);

  async function handleDestroy(deploymentId: string) {
    setBusyId(deploymentId);
    setError('');
    try {
      await api.destroyDeployment(deploymentId);
      await refreshList();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to destroy deployment');
    } finally {
      setBusyId('');
    }
  }

  const emptyState = useMemo(
    () => <p className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-slate-300">No deployments found.</p>,
    []
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Deployments</h1>
        <Link
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          to="/deployments/new"
        >
          New deployment
        </Link>
      </div>

      {loading ? <p className="text-slate-300">Loading deployments...</p> : null}
      {!loading && deployments.length === 0 ? emptyState : null}

      {!loading && deployments.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
          <table className="min-w-full divide-y divide-slate-800 text-sm">
            <thead>
              <tr className="text-left text-slate-300">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {deployments.map((deployment) => (
                <tr key={deployment.id}>
                  <td className="px-4 py-3 text-slate-200">{deployment.name || '(unnamed)'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">{deployment.id}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={deployment.status || deployment.run_status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Link
                        className="rounded border border-slate-700 px-3 py-1 text-xs text-slate-100 hover:bg-slate-800"
                        to={`/deployments/${deployment.id}`}
                      >
                        View
                      </Link>
                      <button
                        type="button"
                        disabled={busyId === deployment.id}
                        onClick={() => void handleDestroy(deployment.id)}
                        className="rounded border border-rose-400/60 px-3 py-1 text-xs text-rose-300 hover:bg-rose-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busyId === deployment.id ? 'Destroying...' : 'Destroy'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {error ? <p className="text-sm text-rose-400">{error}</p> : null}
    </div>
  );
}
