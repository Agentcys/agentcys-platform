import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useApi } from '../hooks/useApi';
import type { ApiCredential } from '../api/client';

export default function SetupPage() {
  const api = useApi();
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey') || '');
  const [credentials, setCredentials] = useState<ApiCredential[]>([]);
  const [selectedCredentialId, setSelectedCredentialId] = useState('');
  const [credentialNameFallback, setCredentialNameFallback] = useState('');
  const [projectId, setProjectId] = useState('');
  const [credentialJsonText, setCredentialJsonText] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    void api
      .listCredentials()
      .then((result) => {
        setCredentials(result);
        if (result.length > 0) {
          setSelectedCredentialId(result[0].id);
        }
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load credentials'));
  }, [api]);

  const credentialOptions = useMemo(
    () => credentials.map((credential) => ({ label: credential.name || credential.id, value: credential.id })),
    [credentials]
  );

  function persistApiKey(event: FormEvent) {
    event.preventDefault();
    localStorage.setItem('apiKey', apiKey.trim());
    setMessage('API key saved.');
    setError('');
  }

  async function handleCredentialUpload(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    setError('');

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(credentialJsonText) as Record<string, unknown>;
    } catch {
      setError('Credential JSON is invalid.');
      return;
    }

    try {
      const created = await api.uploadCredential(parsed);
      setCredentials((prev) => [...prev, created]);
      setSelectedCredentialId(created.id);
      setCredentialJsonText('');
      setMessage('Credential uploaded successfully.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload credential');
    }
  }

  async function handleProjectLink(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    setError('');

    if (!projectId.trim()) {
      setError('Project ID is required.');
      return;
    }

    const payload: Record<string, unknown> = { project_id: projectId.trim() };
    if (selectedCredentialId) {
      payload.credential_id = selectedCredentialId;
    } else if (credentialNameFallback.trim()) {
      payload.credential_name = credentialNameFallback.trim();
    }

    try {
      await api.linkProject(payload);
      setMessage('Project linked successfully.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to link project');
    }
  }

  async function handleCredentialFileUpload(file: File) {
    try {
      const content = await file.text();
      JSON.parse(content);
      setCredentialJsonText(content);
      setError('');
    } catch {
      setError('Selected file does not contain valid JSON.');
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">Setup</h1>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-lg font-medium text-slate-100">API Key</h2>
        <form className="mt-3 flex flex-col gap-3" onSubmit={persistApiKey}>
          <input
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            placeholder="Enter API key"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
          <button className="w-fit rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500" type="submit">
            Save API Key
          </button>
        </form>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-lg font-medium text-slate-100">Upload Credential JSON</h2>
        <form className="mt-3 space-y-3" onSubmit={handleCredentialUpload}>
          <input
            type="file"
            accept="application/json"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void handleCredentialFileUpload(file);
              }
            }}
            className="block text-sm text-slate-300"
          />
          <textarea
            className="min-h-40 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-100"
            placeholder="Paste credential JSON"
            value={credentialJsonText}
            onChange={(event) => setCredentialJsonText(event.target.value)}
          />
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500" type="submit">
            Upload Credential
          </button>
        </form>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-lg font-medium text-slate-100">Link Project</h2>
        <form className="mt-3 space-y-3" onSubmit={handleProjectLink}>
          <input
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            placeholder="Project ID"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
          />
          <label className="block text-sm text-slate-300">Credential dropdown</label>
          <select
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            value={selectedCredentialId}
            onChange={(event) => setSelectedCredentialId(event.target.value)}
          >
            <option value="">Select credential</option>
            {credentialOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <label className="block text-sm text-slate-300">Credential name fallback</label>
          <input
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
            placeholder="credential-name"
            value={credentialNameFallback}
            onChange={(event) => setCredentialNameFallback(event.target.value)}
          />
          <button className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500" type="submit">
            Link Project
          </button>
        </form>
      </section>

      {message ? <p className="text-sm text-emerald-400">{message}</p> : null}
      {error ? <p className="text-sm text-rose-400">{error}</p> : null}
    </div>
  );
}
