import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { ApiBlueprint, ApiProject } from '../api/client';
import JsonSchemaForm from '../components/JsonSchemaForm';
import type { JsonSchema } from '../components/JsonSchemaForm';
import { useApi } from '../hooks/useApi';

function toList<T>(input: unknown): T[] {
  if (Array.isArray(input)) {
    return input as T[];
  }
  if (input && typeof input === 'object') {
    const maybeItems = (input as { items?: unknown }).items;
    if (Array.isArray(maybeItems)) {
      return maybeItems as T[];
    }
  }
  return [];
}

export default function NewDeploymentPage() {
  const api = useApi();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [projectId, setProjectId] = useState('');
  const [blueprintId, setBlueprintId] = useState('');
  const [blueprints, setBlueprints] = useState<ApiBlueprint[]>([]);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [schema, setSchema] = useState<JsonSchema | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    void Promise.all([api.listBlueprints(), api.listProjects()])
      .then(([bpResult, projectResult]) => {
        const nextBlueprints = toList<ApiBlueprint>(bpResult);
        const nextProjects = toList<ApiProject>(projectResult);

        setBlueprints(nextBlueprints);
        setProjects(nextProjects);
        if (nextBlueprints[0]) {
          setBlueprintId(nextBlueprints[0].id);
        }
        if (nextProjects[0]) {
          setProjectId(nextProjects[0].id);
        }
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load blueprints and projects');
      });
  }, [api]);

  useEffect(() => {
    if (!blueprintId) {
      setSchema(null);
      setParameters({});
      return;
    }

    void api
      .getBlueprint(blueprintId)
      .then((blueprint) => {
        setSchema((blueprint.input_schema as JsonSchema) || null);
        setParameters({});
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load blueprint schema');
      });
  }, [api, blueprintId]);

  const canSubmit = useMemo(
    () => !busy && Boolean(name.trim()) && Boolean(projectId) && Boolean(blueprintId) && Object.keys(fieldErrors).length === 0,
    [busy, name, projectId, blueprintId, fieldErrors]
  );

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');

    if (!canSubmit) {
      setError('Please complete the form and resolve validation errors before submitting.');
      return;
    }

    setBusy(true);
    try {
      const created = await api.createDeployment({
        name: name.trim(),
        project_id: projectId,
        blueprint_id: blueprintId,
        parameters,
      });

      navigate(`/deployments/${created.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create deployment');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold text-white">New Deployment</h1>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-4">
        <label className="block space-y-1">
          <span className="text-sm text-slate-100">Deployment name</span>
          <input
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="my-deployment"
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm text-slate-100">Project</span>
          <select
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          >
            <option value="">Select project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name || project.id}
              </option>
            ))}
          </select>
        </label>

        <label className="block space-y-1">
          <span className="text-sm text-slate-100">Blueprint</span>
          <select
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            value={blueprintId}
            onChange={(event) => setBlueprintId(event.target.value)}
          >
            <option value="">Select blueprint</option>
            {blueprints.map((blueprint) => (
              <option key={blueprint.id} value={blueprint.id}>
                {blueprint.name || blueprint.id}
              </option>
            ))}
          </select>
        </label>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-100">Blueprint Parameters</p>
          <JsonSchemaForm
            schema={schema}
            value={parameters}
            onChange={setParameters}
            onValidationChange={setFieldErrors}
          />
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? 'Creating deployment...' : 'Create deployment'}
        </button>
      </form>

      {error ? <p className="text-sm text-rose-400">{error}</p> : null}
    </div>
  );
}
