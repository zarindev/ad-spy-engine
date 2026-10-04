/** Shared Recharts tooltip in app tokens (text never wears the series color). */
export function ChartTooltip({ active, payload, label, unit = "", labelFormat }: {
  active?: boolean;
  payload?: { value: number; name?: string }[];
  label?: string | number;
  unit?: string;
  labelFormat?: (l: string | number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-xl">
      <div className="text-muted-foreground">{label !== undefined && labelFormat ? labelFormat(label) : label}</div>
      <div className="num mt-0.5 text-sm font-semibold text-foreground">
        {payload[0].value.toLocaleString()}
        {unit}
      </div>
    </div>
  );
}
