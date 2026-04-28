type JsonSchema = {
  type?: string;
  title?: string;
  default?: unknown;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  additionalProperties?: JsonSchema | boolean;
};

type JsonSchemaFormProps = {
  schema: JsonSchema | null;
  value: Record<string, unknown>;
  onChange: (nextValue: Record<string, unknown>) => void;
};

export default function JsonSchemaForm({ schema }: JsonSchemaFormProps) {
  return (
    <div className="rounded border border-slate-700 bg-slate-950 p-4 text-sm text-slate-300">
      {schema ? 'Schema fields will render here.' : 'Select a blueprint to load schema.'}
    </div>
  );
}
