import { useState, useEffect } from "react";

const TODO_DATA = [
  {
    category: "🧠 Smarter Extraction",
    color: "violet",
    items: [
      {
        id: "jsonld",
        title: "JSON-LD / schema.org parsing",
        detail: "Parse <script type=\"application/ld+json\"> blocks before falling back to regex. Fast, free, and dramatically improves accuracy on modern hospital sites.",
        priority: "high",
        effort: "Low",
      },
      {
        id: "claude-api",
        title: "Anthropic API integration",
        detail: "Use Claude to read messy, unstructured HTML and extract fields that regex misses entirely. Single biggest quality jump available.",
        priority: "high",
        effort: "Medium",
      },
      {
        id: "nppes-bulk",
        title: "NPPES bulk enrichment pass",
        detail: "After a job finishes, run a second pass to fill in missing NPIs and pull back additional fields: practice address, phone, taxonomy code.",
        priority: "medium",
        effort: "Low",
      },
    ],
  },
  {
    category: "⚡ Performance",
    color: "amber",
    items: [
      {
        id: "parallel-fetch",
        title: "Parallel page fetching",
        detail: "Replace sequential fetching (0.5s delay) with asyncio + httpx for 5–10 concurrent requests. Could make jobs 5–10× faster.",
        priority: "high",
        effort: "Medium",
      },
      {
        id: "async-fastapi",
        title: "Async FastAPI + background tasks",
        detail: "Migrate from threading.Thread to asyncio background tasks for cleaner concurrency handling at scale.",
        priority: "medium",
        effort: "Medium",
      },
      {
        id: "redis-celery",
        title: "Redis + Celery job queue",
        detail: "Persist jobs across server restarts, support retries, and allow multiple worker processes. Right now jobs live in memory only.",
        priority: "low",
        effort: "High",
      },
    ],
  },
  {
    category: "💾 Data & Storage",
    color: "emerald",
    items: [
      {
        id: "sqlite",
        title: "SQLite / PostgreSQL backend",
        detail: "Store all extracted records in a database so you can query, filter, deduplicate across jobs, and export on demand rather than one CSV per job.",
        priority: "high",
        effort: "Medium",
      },
      {
        id: "cross-job-dedup",
        title: "Cross-job deduplication",
        detail: "Each job deduplicates internally, but scraping the same hospital twice creates duplicates across CSVs. A DB unique index on (first_name, last_name, npi) solves this permanently.",
        priority: "high",
        effort: "Low",
      },
      {
        id: "gsheets",
        title: "Google Sheets export",
        detail: "Export directly to Google Sheets using gspread + a Service Account. Schema is now stable enough to add this cleanly.",
        priority: "medium",
        effort: "Low",
      },
    ],
  },
  {
    category: "🖥️ UI / UX",
    color: "sky",
    items: [
      {
        id: "results-table",
        title: "Results preview table in browser",
        detail: "Show extracted doctors directly in the UI before downloading — sortable columns, inline editing to fix mistakes.",
        priority: "high",
        effort: "Medium",
      },
      {
        id: "bulk-urls",
        title: "Bulk URL input",
        detail: "Paste a list of 10+ hospital URLs and kick off all jobs at once instead of one at a time.",
        priority: "medium",
        effort: "Low",
      },
      {
        id: "confidence-score",
        title: "Extraction confidence score",
        detail: "Flag records where extraction is uncertain (e.g. name found but no email/phone) so you know which rows need manual review.",
        priority: "medium",
        effort: "Medium",
      },
      {
        id: "scheduling",
        title: "Job scheduling / recurring scrapes",
        detail: "Schedule recurring scrapes (e.g. re-scrape every 30 days) to keep data fresh automatically.",
        priority: "low",
        effort: "High",
      },
    ],
  },
  {
    category: "🔒 Reliability & Compliance",
    color: "rose",
    items: [
      {
        id: "rate-limit",
        title: "Per-domain rate limiting",
        detail: "Currently all domains get the same 0.5s delay. Configurable per-domain delays would be more respectful and reduce blocks.",
        priority: "medium",
        effort: "Low",
      },
      {
        id: "ua-rotation",
        title: "User-agent rotation",
        detail: "Cycle through realistic browser user-agent strings to reduce bot detection on aggressive sites.",
        priority: "medium",
        effort: "Low",
      },
      {
        id: "proxy-rotation",
        title: "Proxy rotation",
        detail: "Integrate a proxy pool (e.g. Bright Data, Oxylabs) for large-scale scraping where sites block repeated requests from the same IP.",
        priority: "low",
        effort: "High",
      },
      {
        id: "audit-log",
        title: "Export audit log",
        detail: "Track what was scraped, when, and by whom. Useful when sharing the tool with a team.",
        priority: "low",
        effort: "Low",
      },
    ],
  },
];

const PRIORITY_STYLES = {
  high: { label: "High", bg: "bg-red-100", text: "text-red-700", dot: "bg-red-500" },
  medium: { label: "Med", bg: "bg-yellow-100", text: "text-yellow-700", dot: "bg-yellow-500" },
  low: { label: "Low", bg: "bg-gray-100", text: "text-gray-500", dot: "bg-gray-400" },
};

const EFFORT_STYLES = {
  Low: "text-emerald-600",
  Medium: "text-amber-600",
  High: "text-rose-600",
};

const COLOR_MAP = {
  violet: { header: "bg-violet-600", light: "bg-violet-50", border: "border-violet-200", accent: "text-violet-700" },
  amber:  { header: "bg-amber-500",  light: "bg-amber-50",  border: "border-amber-200",  accent: "text-amber-700"  },
  emerald:{ header: "bg-emerald-600",light: "bg-emerald-50",border: "border-emerald-200",accent: "text-emerald-700"},
  sky:    { header: "bg-sky-600",    light: "bg-sky-50",    border: "border-sky-200",    accent: "text-sky-700"    },
  rose:   { header: "bg-rose-600",   light: "bg-rose-50",   border: "border-rose-200",   accent: "text-rose-700"   },
};

const RECOMMENDED_IDS = ["jsonld", "parallel-fetch", "sqlite", "cross-job-dedup", "results-table"];

function useStorage() {
  const [done, setDone] = useState({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const result = await window.storage.get("scraper-todos-done");
        if (result) setDone(JSON.parse(result.value));
      } catch (_) {}
      setLoaded(true);
    })();
  }, []);

  const toggle = async (id) => {
    const next = { ...done, [id]: !done[id] };
    if (!next[id]) delete next[id];
    setDone(next);
    try {
      await window.storage.set("scraper-todos-done", JSON.stringify(next));
    } catch (_) {}
  };

  return { done, toggle, loaded };
}

export default function App() {
  const { done, toggle, loaded } = useStorage();
  const [filter, setFilter] = useState("all");

  const allItems = TODO_DATA.flatMap(c => c.items);
  const completedCount = allItems.filter(i => done[i.id]).length;
  const totalCount = allItems.length;

  const filterOptions = [
    { value: "all", label: "All" },
    { value: "high", label: "🔴 High Priority" },
    { value: "recommended", label: "⭐ Recommended First" },
    { value: "pending", label: "⬜ Pending" },
    { value: "done", label: "✅ Done" },
  ];

  const shouldShowItem = (item) => {
    if (filter === "all") return true;
    if (filter === "high") return item.priority === "high";
    if (filter === "recommended") return RECOMMENDED_IDS.includes(item.id);
    if (filter === "pending") return !done[item.id];
    if (filter === "done") return !!done[item.id];
    return true;
  };

  const pct = Math.round((completedCount / totalCount) * 100);

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Hospital Scraper · Improvement Roadmap</h1>
          <p className="text-gray-500 text-sm mt-1">{totalCount} improvements across 5 categories</p>
        </div>

        {/* Progress */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-5 flex items-center gap-4">
          <div className="flex-1">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600 font-medium">Progress</span>
              <span className="text-gray-900 font-semibold">{completedCount} / {totalCount} done</span>
            </div>
            <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
          <div className="text-2xl font-bold text-emerald-600 w-12 text-right">{pct}%</div>
        </div>

        {/* Recommended banner */}
        {filter !== "recommended" && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3.5 mb-5 flex items-start gap-3">
            <span className="text-amber-500 text-lg mt-0.5">⭐</span>
            <div>
              <p className="text-amber-800 text-sm font-semibold">Recommended starting point</p>
              <p className="text-amber-700 text-xs mt-0.5">
                JSON-LD parsing → Parallel fetching → SQLite + cross-job dedup → Results preview table
              </p>
            </div>
            <button
              onClick={() => setFilter("recommended")}
              className="ml-auto text-xs font-semibold text-amber-700 bg-amber-100 hover:bg-amber-200 px-2.5 py-1 rounded-lg whitespace-nowrap"
            >
              Show only these
            </button>
          </div>
        )}

        {/* Filter bar */}
        <div className="flex gap-2 flex-wrap mb-5">
          {filterOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
                filter === opt.value
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Categories */}
        <div className="space-y-5">
          {TODO_DATA.map((cat) => {
            const visibleItems = cat.items.filter(shouldShowItem);
            if (visibleItems.length === 0) return null;
            const colors = COLOR_MAP[cat.color];
            const catDone = cat.items.filter(i => done[i.id]).length;

            return (
              <div key={cat.category} className={`rounded-xl border ${colors.border} overflow-hidden`}>
                {/* Category header */}
                <div className={`${colors.header} px-4 py-3 flex items-center justify-between`}>
                  <span className="text-white font-semibold text-sm">{cat.category}</span>
                  <span className="text-white/80 text-xs">{catDone}/{cat.items.length}</span>
                </div>

                {/* Items */}
                <div className={`${colors.light} divide-y ${colors.border}`}>
                  {visibleItems.map((item) => {
                    const isDone = !!done[item.id];
                    const pStyle = PRIORITY_STYLES[item.priority];
                    const isRec = RECOMMENDED_IDS.includes(item.id);

                    return (
                      <div
                        key={item.id}
                        className={`px-4 py-3.5 flex gap-3 cursor-pointer transition-opacity ${isDone ? "opacity-50" : "opacity-100"}`}
                        onClick={() => toggle(item.id)}
                      >
                        {/* Checkbox */}
                        <div className="mt-0.5 shrink-0">
                          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                            isDone ? "bg-emerald-500 border-emerald-500" : "border-gray-300 bg-white"
                          }`}>
                            {isDone && <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>}
                          </div>
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`text-sm font-semibold text-gray-800 ${isDone ? "line-through text-gray-400" : ""}`}>
                              {item.title}
                            </span>
                            {isRec && !isDone && (
                              <span className="text-xs bg-amber-100 text-amber-700 font-semibold px-1.5 py-0.5 rounded">⭐ Do first</span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{item.detail}</p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${pStyle.bg} ${pStyle.text}`}>
                              {pStyle.label} priority
                            </span>
                            <span className={`text-xs font-medium ${EFFORT_STYLES[item.effort]}`}>
                              {item.effort} effort
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {filter !== "all" && (
          <button onClick={() => setFilter("all")} className="mt-4 text-sm text-gray-400 hover:text-gray-600 underline">
            ← Show all items
          </button>
        )}

        <p className="text-center text-xs text-gray-300 mt-8">Progress is saved automatically</p>
      </div>
    </div>
  );
}
