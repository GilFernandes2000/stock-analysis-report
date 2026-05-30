interface ReportViewerProps {
  markdown: string;
}

export function ReportViewer({ markdown }: ReportViewerProps) {
  const lines = markdown.split("\n");

  return (
    <div className="prose prose-invert max-w-none space-y-2 text-sm">
      {lines.map((line, i) => {
        if (line.startsWith("# ")) {
          return (
            <h2 key={i} className="text-xl font-bold text-white">
              {line.slice(2)}
            </h2>
          );
        }
        if (line.startsWith("**")) {
          const text = line.replace(/\*\*/g, "");
          return (
            <p key={i} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-slate-200">
              {text}
            </p>
          );
        }
        if (line.startsWith("_") && line.endsWith("_")) {
          return (
            <p key={i} className="italic text-slate-400">
              {line.slice(1, -1)}
            </p>
          );
        }
        if (!line.trim()) return <div key={i} className="h-2" />;
        return (
          <p key={i} className="text-slate-300">
            {line}
          </p>
        );
      })}
    </div>
  );
}
