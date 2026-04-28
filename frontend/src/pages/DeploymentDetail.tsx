import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { ApiDeployment } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import { useApi } from '../hooks/useApi';
import { usePolling } from '../hooks/usePolling';

const ACTIVE_STATUSES = new Set(['pending', 'applying', 'destroying']);

export default function DeploymentDetailPage() {
  const { deploymentId = '' } = useParams();
  const api = useApi();
  const [deployment, setDeployment] = useState<ApiDeployment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (!deploymentId) {
      return;
    }

    try {
      const result = await api.getDeployment(deploymentId);
      setDeployment(result);
      setError('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load deployment');
    } finally {
      setLoading(false);
    }
  }, [api, deploymentId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const currentStatus = useMemo(
    () => (deployment?.status || deployment?.run_status || 'unknown').toLowerCase(),
    [deployment]
  );

  usePolling(
    () => {
      void refresh();
    },
    {
      enabled: ACTIVE_STATUSES.has(currentStatus),
      intervalMs: 5000,
    }
  );

  if (!deploymentId) {
    return <p className="text-rose-400">Missing deployment id.</p>;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Deployment Detail</h1>
        <Link to="/deployments" className="text-sm text-indigo-300 hover:text-indigo-200">
          Back to list
        </Link>
      </div>

      {loading ? <p className="text-slate-300">Loading deployment...</p> : null}

      {deployment ? (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Name</dt>
              <dd className="text-slate-100">{deployment.name || '(unnamed)'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Deployment ID</dt>
              <dd className="font-mono text-xs text-slate-300">{deployment.id}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Deployment Status</dt>
              <dd>
                <StatusBadge status={deployment.status} />
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Run Status</dt>
              <dd>
                <StatusBadge status={deployment.run_status} />
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Project</dt>
              <dd className="text-slate-200">{deployment.project_id || 'N/A'}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Blueprint</dt>
              <dd className="text-slate-200">{deployment.blueprint_id || 'N/A'}</dd>
            </div>
          </dl>

          {ACTIVE_STATUSES.has(currentStatus) ? (
            <p className="mt-4 text-xs text-sky-300">Auto-refreshing every 5 seconds while deployment is in progress.</p>
          ) : null}
        </div>
      ) : null}

      {error ? <p className="text-sm text-rose-400">{error}</p> : null}
    </div>
  );
}
