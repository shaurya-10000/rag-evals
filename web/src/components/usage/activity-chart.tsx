import { format, parseISO } from 'date-fns';

type Props = { data: { date: string; count: number }[] };

export function ActivityChart({ data }: Props) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const first = data[0];
  const last = data[data.length - 1];

  return (
    <div>
      <div
        className="flex h-32 items-end gap-1.5"
        role="img"
        aria-label={`Questions asked per day over the last ${data.length} days`}
      >
        {data.map((day) => (
          <div
            key={day.date}
            title={`${format(parseISO(day.date), 'MMM d')}: ${day.count}`}
            className="group flex h-full flex-1 flex-col justify-end"
          >
            <div
              className="w-full rounded-t-md bg-accent-500/70 transition-colors group-hover:bg-accent-500"
              style={{ height: `${(day.count / max) * 100}%`, minHeight: day.count > 0 ? 4 : 2 }}
            />
          </div>
        ))}
      </div>
      {first && last && (
        <div className="mt-1.5 flex justify-between text-[10px] text-neutral-500">
          <span>{format(parseISO(first.date), 'MMM d')}</span>
          <span>{format(parseISO(last.date), 'MMM d')}</span>
        </div>
      )}
    </div>
  );
}
