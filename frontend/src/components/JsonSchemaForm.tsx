import { useEffect, useMemo } from 'react';

export type JsonSchema = {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  additionalProperties?: JsonSchema | boolean;
};

type JsonSchemaFormProps = {
  schema: JsonSchema | null;
  value: Record<string, unknown>;
  onChange: (nextValue: Record<string, unknown>) => void;
  onValidationChange?: (errors: Record<string, string>) => void;
};

function withDefaults(schema: JsonSchema, current: Record<string, unknown>): Record<string, unknown> {
  const next = { ...current };
  const properties = schema.properties || {};

  for (const [key, fieldSchema] of Object.entries(properties)) {
    if (next[key] !== undefined) {
      continue;
    }
    if (fieldSchema.default !== undefined) {
      next[key] = fieldSchema.default;
      continue;
    }
    if (fieldSchema.type === 'boolean') {
      next[key] = false;
    }
  }

  return next;
}

function validate(schema: JsonSchema, value: Record<string, unknown>): Record<string, string> {
  const errors: Record<string, string> = {};
  const required = new Set(schema.required || []);
  const properties = schema.properties || {};

  for (const [key, fieldSchema] of Object.entries(properties)) {
    const rawValue = value[key];
    const isRequired = required.has(key);

    if (isRequired) {
      if (rawValue === undefined || rawValue === null || rawValue === '') {
        errors[key] = 'Required field';
        continue;
      }
    }

    if (fieldSchema.type === 'number' && rawValue !== undefined && rawValue !== null && rawValue !== '') {
      if (typeof rawValue !== 'number' || Number.isNaN(rawValue)) {
        errors[key] = 'Must be a valid number';
      }
    }

    if (fieldSchema.type === 'object' && rawValue !== undefined && rawValue !== null) {
      if (typeof rawValue !== 'object' || Array.isArray(rawValue)) {
        errors[key] = 'Must be an object map';
      }
    }
  }

  return errors;
}

export default function JsonSchemaForm({ schema, value, onChange, onValidationChange }: JsonSchemaFormProps) {
  useEffect(() => {
    if (!schema) {
      return;
    }

    const next = withDefaults(schema, value);
    if (JSON.stringify(next) !== JSON.stringify(value)) {
      onChange(next);
    }
  }, [schema]);

  const validationErrors = useMemo(() => {
    if (!schema) {
      return {};
    }
    return validate(schema, value);
  }, [schema, value]);

  useEffect(() => {
    onValidationChange?.(validationErrors);
  }, [validationErrors, onValidationChange]);

  function setFieldValue(name: string, nextValue: unknown) {
    onChange({
      ...value,
      [name]: nextValue,
    });
  }

  if (!schema) {
    return <div className="rounded border border-slate-700 bg-slate-950 p-4 text-sm text-slate-300">Select a blueprint to load schema.</div>;
  }

  const properties = schema.properties || {};
  const required = new Set(schema.required || []);

  return (
    <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-4">
      {Object.entries(properties).map(([fieldName, fieldSchema]) => {
        const fieldValue = value[fieldName];
        const error = validationErrors[fieldName];
        const label = fieldSchema.title || fieldName;
        const isRequired = required.has(fieldName);

        if (fieldSchema.type === 'boolean') {
          return (
            <label key={fieldName} className="flex items-center gap-3 text-sm text-slate-100">
              <input
                type="checkbox"
                checked={Boolean(fieldValue)}
                onChange={(event) => setFieldValue(fieldName, event.target.checked)}
              />
              <span>
                {label} {isRequired ? <span className="text-rose-300">*</span> : null}
              </span>
            </label>
          );
        }

        if (fieldSchema.type === 'object' && fieldSchema.additionalProperties && typeof fieldSchema.additionalProperties === 'object') {
          const mapValue =
            fieldValue && typeof fieldValue === 'object' && !Array.isArray(fieldValue)
              ? (fieldValue as Record<string, string>)
              : {};

          return (
            <div key={fieldName} className="space-y-2">
              <p className="text-sm font-medium text-slate-100">
                {label} {isRequired ? <span className="text-rose-300">*</span> : null}
              </p>
              <div className="space-y-2">
                {Object.entries(mapValue).map(([entryKey, entryValue]) => (
                  <div key={entryKey} className="flex items-center gap-2">
                    <input
                      className="w-1/2 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                      value={entryKey}
                      onChange={(event) => {
                        const next = { ...mapValue };
                        delete next[entryKey];
                        next[event.target.value] = entryValue;
                        setFieldValue(fieldName, next);
                      }}
                    />
                    <input
                      className="w-1/2 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                      value={entryValue}
                      onChange={(event) => {
                        setFieldValue(fieldName, {
                          ...mapValue,
                          [entryKey]: event.target.value,
                        });
                      }}
                    />
                    <button
                      type="button"
                      className="rounded border border-rose-400/70 px-2 py-1 text-xs text-rose-300"
                      onClick={() => {
                        const next = { ...mapValue };
                        delete next[entryKey];
                        setFieldValue(fieldName, next);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                className="rounded border border-slate-600 px-3 py-1 text-xs text-slate-200"
                onClick={() => {
                  let nextKey = 'key';
                  let counter = 1;
                  while (mapValue[nextKey] !== undefined) {
                    counter += 1;
                    nextKey = `key_${counter}`;
                  }
                  setFieldValue(fieldName, {
                    ...mapValue,
                    [nextKey]: '',
                  });
                }}
              >
                Add entry
              </button>
              {error ? <p className="text-xs text-rose-400">{error}</p> : null}
            </div>
          );
        }

        if (fieldSchema.type === 'number') {
          return (
            <label key={fieldName} className="block space-y-1">
              <span className="text-sm text-slate-100">
                {label} {isRequired ? <span className="text-rose-300">*</span> : null}
              </span>
              <input
                type="number"
                className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                value={fieldValue === undefined || fieldValue === null ? '' : String(fieldValue)}
                onChange={(event) => {
                  const raw = event.target.value;
                  setFieldValue(fieldName, raw === '' ? undefined : Number(raw));
                }}
              />
              {error ? <p className="text-xs text-rose-400">{error}</p> : null}
            </label>
          );
        }

        return (
          <label key={fieldName} className="block space-y-1">
            <span className="text-sm text-slate-100">
              {label} {isRequired ? <span className="text-rose-300">*</span> : null}
            </span>
            <input
              type="text"
              className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
              value={fieldValue === undefined || fieldValue === null ? '' : String(fieldValue)}
              onChange={(event) => setFieldValue(fieldName, event.target.value)}
            />
            {fieldSchema.description ? <p className="text-xs text-slate-400">{fieldSchema.description}</p> : null}
            {error ? <p className="text-xs text-rose-400">{error}</p> : null}
          </label>
        );
      })}
    </div>
  );
}
