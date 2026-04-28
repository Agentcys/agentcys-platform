type StatusBadgeProps = {
  status?: string;
};

const paletteByStatus: Record<string, string> = {
  pending: 'bg-amber-500/20 text-amber-300 ring-amber-500/30',
  applying: 'bg-sky-500/20 text-sky-300 ring-sky-500/30',
  destroying: 'bg-rose-500/20 text-rose-300 ring-rose-500/30',
  success: 'bg-emerald-500/20 text-emerald-300 ring-emerald-500/30',
  failed: 'bg-red-500/20 text-red-200 ring-red-500/30',
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = (status || 'unknown').toLowerCase();
  const classes = paletteByStatus[normalized] || 'bg-slate-500/20 text-slate-200 ring-slate-500/30';

  return <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${classes}`}>{normalized}</span>;
}
