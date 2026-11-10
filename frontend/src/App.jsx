/**
 * Enterprise Multi-Cloud Disaster Recovery Control Plane (Mission Control)
 *
 * Core architecture:
 * - Dynamic real-time telemetry from FastAPI backend (/api/*)
 * - Server-Sent Events (SSE) live workflow runner with stopwatch
 * - Real-time PaySim transaction ingestion and cross-cloud replication
 * - Autonomous 3-strike watchdog sentry with failover/failback
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRightLeft,
  RotateCcw,
  Zap,
} from 'lucide-react';

import OnboardingModal from './components/OnboardingModal';
import WorkloadHydrationMatrix from './components/WorkloadHydrationMatrix';
import LiveTransactionStream from './components/LiveTransactionStream';
import Sidebar from './components/Sidebar';
import DashboardHeader from './components/DashboardHeader';
import LiveExecutionConsole from './components/LiveExecutionConsole';
import ObjectLedgerTable from './components/ObjectLedgerTable';

export default function App() {
  const [apiOnline, setApiOnline] = useState(true);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [copiedHandle, setCopiedHandle] = useState(false);
  const [tableSearch, setTableSearch] = useState('');
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [readyToast, setReadyToast] = useState(null);
  const hasPromptedOnboarding = useRef(false);

  // Live telemetry state from /api/* (Zero hardcoded fake fixtures)
  const [status, setStatus] = useState(null);
  const [kpis, setKpis] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [drillHistory, setDrillHistory] = useState([]);
  const [liveLogs, setLiveLogs] = useState([]);

  // GitHub Actions-Style Live Workflow Runner State
  const [consoleTab, setConsoleTab] = useState('workflow'); // 'workflow' | 'probes'
  const [workflowRun, setWorkflowRun] = useState({
    runId: null,
    workflow: null,
    title: 'Ready — Trigger any Failover, Failback, or Live Reconcile in the console below',
    state: 'idle', // 'idle' | 'running' | 'success' | 'error'
    startedAtMs: null,
    elapsedS: 0,
    activeStepIdx: -1,
    stepStartedAtMs: null,
    stepElapsedS: 0,
    steps: [],
  });

  const consoleRef = useRef(null);

  // ---------------------------------------------------------------------------
  // Polling Hook: Fetch real telemetry from backend
  // ---------------------------------------------------------------------------
  const fetchTelemetry = useCallback(async () => {
    const safeJson = async (url, fallback = null) => {
      const r = await fetch(url);
      if (!r.ok) return fallback;
      const ct = r.headers.get('content-type') || '';
      if (!ct.includes('application/json')) return fallback;
      return r.json();
    };
    try {
      const [resStatus, resKpis, resDiag, resLedger, resDrills, resLogs, resLastRun] = await Promise.all([
        safeJson('/api/status', null),
        safeJson('/api/kpi', []),
        safeJson('/api/diagnostics', null),
        safeJson('/api/ledger', null),
        safeJson('/api/drills', []),
        safeJson('/api/live-logs', []),
        safeJson('/api/workflows/last-run', null),
      ]);

      setApiOnline(true);
      if (resStatus) {
        setStatus(resStatus);
        if (!hasPromptedOnboarding.current && resStatus.is_configured === false) {
          hasPromptedOnboarding.current = true;
          setShowOnboarding(true);
        }
      }
      if (resKpis) setKpis(resKpis);
      if (resDiag) setDiagnostics(resDiag);
      if (resLedger) setLedger(resLedger);
      if (resDrills) setDrillHistory(resDrills);
      if (resLogs) setLiveLogs(resLogs);

      // Hydrate last workflow run on initial load
      if (resLastRun && workflowRun.state === 'idle') {
        setWorkflowRun((prev) => ({
          ...prev,
          runId: resLastRun.run_id,
          workflow: resLastRun.workflow,
          title: `${resLastRun.title} (Completed in ${resLastRun.duration_s || 0}s)`,
          state: resLastRun.state || 'success',
          elapsedS: resLastRun.duration_s || 0,
          steps: (resLastRun.steps || []).map((s) => ({
            name: s.name,
            status: s.status,
            durationS: s.duration_s,
            expanded: false,
            logs: s.logs || [],
          })),
        }));
      }
    } catch {
      setApiOnline(false);
    }
  }, [workflowRun.state]);

  useEffect(() => {
    fetchTelemetry();
    if (!autoRefresh) return;
    const interval = setInterval(fetchTelemetry, 2500);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchTelemetry]);

  // ---------------------------------------------------------------------------
  // Live Stopwatch Effect
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (workflowRun.state !== 'running' || !workflowRun.startedAtMs) return;
    const tick = setInterval(() => {
      const now = Date.now();
      const totalElapsed = parseFloat(((now - workflowRun.startedAtMs) / 1000).toFixed(1));
      setWorkflowRun((prev) => ({ ...prev, elapsedS: totalElapsed }));
    }, 100);
    return () => clearInterval(tick);
  }, [workflowRun.state, workflowRun.startedAtMs]);

  // ---------------------------------------------------------------------------
  // Execute Workflow via Server-Sent Events (SSE)
  // ---------------------------------------------------------------------------
  const startLiveWorkflow = useCallback(
    async (workflowType) => {
      if (workflowRun.state === 'running') return;

      const runId = `RUN-${Date.now().toString().slice(-6)}`;
      const startTime = Date.now();
      setConsoleTab('workflow');

      setWorkflowRun({
        runId,
        workflow: workflowType,
        title: `Executing ${workflowType.toUpperCase()} Workflow (${runId})...`,
        state: 'running',
        startedAtMs: startTime,
        elapsedS: 0,
        activeStepIdx: 0,
        stepStartedAtMs: startTime,
        stepElapsedS: 0,
        steps: [],
      });

      if (consoleRef.current) {
        consoleRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      try {
        const url = `/api/workflows/live-stream?workflow=${encodeURIComponent(workflowType)}`;
        const es = new EventSource(url);
        let finished = false;

        es.onmessage = (ev) => {
          if (!ev.data) return;
          let msg;
          try {
            msg = JSON.parse(ev.data);
          } catch {
            return;
          }

          if (msg.type === 'workflow_init') {
            setWorkflowRun((prev) => ({
              ...prev,
              runId: msg.run_id || prev.runId,
              title: `${msg.title} (${msg.run_id || prev.runId})`,
              steps: (msg.steps || []).map((st, i) => ({
                idx: i,
                name: typeof st === 'string' ? st : st.name,
                status: i === 0 ? 'running' : 'queued',
                durationS: null,
                logs: [],
                expanded: i === 0,
              })),
            }));
          } else if (msg.type === 'step_start') {
            const idx = msg.step_index;
            setWorkflowRun((prev) => ({
              ...prev,
              activeStepIdx: idx,
              stepStartedAtMs: Date.now(),
              steps: prev.steps.map((st, i) =>
                i === idx ? { ...st, status: 'running', expanded: true } : st
              ),
            }));
          } else if (msg.type === 'step_log') {
            const stepIdx = msg.step_index ?? 0;
            setWorkflowRun((prev) => ({
              ...prev,
              steps: prev.steps.map((st, i) =>
                i === stepIdx ? { ...st, logs: [...st.logs, msg] } : st
              ),
            }));
          } else if (msg.type === 'step_done') {
            const idx = msg.step_index;
            setWorkflowRun((prev) => ({
              ...prev,
              steps: prev.steps.map((st, i) =>
                i === idx
                  ? { ...st, status: 'done', durationS: msg.duration_s, expanded: false }
                  : i === idx + 1
                  ? { ...st, status: 'running', expanded: true }
                  : st
              ),
            }));
          } else if (msg.type === 'telemetry_refresh') {
            fetchTelemetry();
          } else if (msg.type === 'workflow_done') {
            finished = true;
            es.close();
            const totalDuration = msg.total_s ?? parseFloat(((Date.now() - startTime) / 1000).toFixed(2));
            setWorkflowRun((prev) => ({
              ...prev,
              state: 'success',
              elapsedS: totalDuration,
              title: msg.summary || `${workflowType.toUpperCase()} Complete (${totalDuration}s)`,
            }));
            fetchTelemetry();
          } else if (msg.type === 'workflow_error') {
            finished = true;
            es.close();
            const totalDuration = parseFloat(((Date.now() - startTime) / 1000).toFixed(2));
            setWorkflowRun((prev) => ({
              ...prev,
              state: 'error',
              elapsedS: totalDuration,
              title: `Workflow Error: ${msg.error || 'Execution failed'}`,
              steps: prev.steps.map((st) =>
                st.status === 'running'
                  ? {
                      ...st,
                      status: 'error',
                      expanded: true,
                      logs: [...st.logs, { ts: msg.ts || '', level: 'ERROR', message: msg.error || 'Execution failed' }],
                    }
                  : st
              ),
            }));
            fetchTelemetry();
          }
        };

        es.onerror = () => {
          if (finished) return;
          es.close();
          const totalDuration = parseFloat(((Date.now() - startTime) / 1000).toFixed(2));
          setWorkflowRun((prev) => ({
            ...prev,
            state: 'error',
            elapsedS: totalDuration,
            title: `Workflow execution failed or connection interrupted`,
          }));
          fetchTelemetry();
        };
      } catch {
        setWorkflowRun((prev) => ({
          ...prev,
          state: 'error',
          title: 'Failed to initiate workflow stream',
        }));
      }
    },
    [fetchTelemetry, workflowRun.state]
  );

  const toggleStepExpand = (stepIdx) => {
    setWorkflowRun((prev) => ({
      ...prev,
      steps: prev.steps.map((s, i) => (i === stepIdx ? { ...s, expanded: !s.expanded } : s)),
    }));
  };

  const handleToggleAwsOutage = async (enableOutage) => {
    try {
      await fetch('/api/watchdog/outage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulate: enableOutage }),
      });
      fetchTelemetry();
    } catch {
      // ignore
    }
  };

  const handleDownloadPdfReport = async () => {
    try {
      setDownloadingPdf(true);
      const res = await fetch('/api/reports/executive-pdf');
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Snowflake_MultiCloud_DR_Compliance_Audit_${new Date().toISOString().slice(0, 10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }
    } catch {
      // ignore
    } finally {
      setDownloadingPdf(false);
    }
  };

  const copyHandle = () => {
    if (status?.global_redirect_handle) {
      navigator.clipboard.writeText(status.global_redirect_handle);
      setCopiedHandle(true);
      setTimeout(() => setCopiedHandle(false), 2000);
    }
  };

  // Telemetry Snapshot references
  const awsSnap = status?.aws || diagnostics?.aws || null;
  const azSnap = status?.azure || diagnostics?.azure || null;
  const anycastSnap = status?.anycast || diagnostics?.anycast || null;
  const totalCreditsUsed =
    awsSnap?.used_credits != null && azSnap?.used_credits != null
      ? (awsSnap.used_credits + azSnap.used_credits).toFixed(2)
      : '--';
  const totalCreditQuota =
    awsSnap?.credit_quota != null && azSnap?.credit_quota != null
      ? (awsSnap.credit_quota + azSnap.credit_quota).toFixed(1)
      : '--';
  const creditPct =
    totalCreditsUsed !== '--' && totalCreditQuota !== '--'
      ? Math.min(100, (parseFloat(totalCreditsUsed) / parseFloat(totalCreditQuota)) * 100)
      : 0;

  // Real Dynamic SVG Polyline from live telemetry_timeline
  const timeline = diagnostics?.telemetry_timeline || [];
  const maxPing = Math.max(500, ...timeline.map((p) => Math.max(p.aws_ping_ms || 0, p.azure_ping_ms || 0)));
  const buildPolyline = (key) => {
    if (timeline.length === 0) return '';
    if (timeline.length === 1) {
      const y = 75 - Math.min(70, ((timeline[0][key] || 0) / maxPing) * 70);
      return `0,${y.toFixed(1)} 300,${y.toFixed(1)}`;
    }
    return timeline
      .map((pt, idx) => {
        const x = (idx / (timeline.length - 1)) * 300;
        const y = 75 - Math.min(70, ((pt[key] || 0) / maxPing) * 70);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  };

  const isWorkflowBusy = workflowRun.state === 'running';

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col md:flex-row text-slate-800">
      {/* ============================================================== */}
      {/* MODULAR SIDEBAR: Multi-Cloud Connectivity & Watchdog Controls  */}
      {/* ============================================================== */}
      <Sidebar
        apiOnline={apiOnline}
        status={status}
        awsSnap={awsSnap}
        azSnap={azSnap}
        anycastSnap={anycastSnap}
        totalCreditsUsed={totalCreditsUsed}
        totalCreditQuota={totalCreditQuota}
        creditPct={creditPct}
        copiedHandle={copiedHandle}
        copyHandle={copyHandle}
      />

      {/* ============================================================== */}
      {/* MAIN CONTENT AREA                                              */}
      {/* ============================================================== */}
      <main className="flex-1 flex flex-col min-w-0 max-w-full overflow-x-hidden overflow-y-auto">
        {!apiOnline && (
          <div className="bg-red-600 text-white px-6 py-2.5 text-xs font-bold flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4" />
              <span>
                Backend API on http://127.0.0.1:8000 is not reachable. Ensure FastAPI server is running.
              </span>
            </div>
            <button onClick={fetchTelemetry} className="px-2.5 py-1 bg-white text-red-700 rounded font-black cursor-pointer">
              Retry Now
            </button>
          </div>
        )}

        {/* Modular Executive Header Bar */}
        <DashboardHeader
          status={status}
          downloadingPdf={downloadingPdf}
          handleDownloadPdfReport={handleDownloadPdfReport}
          setShowOnboarding={setShowOnboarding}
        />

        <div className="p-6 space-y-6">
          {/* SaaS Setup Banner when unconfigured */}
          {status && status.is_configured === false && (
            <div className="bg-gradient-to-r from-blue-950 via-indigo-950 to-slate-900 border border-blue-500/50 rounded-xl p-5 text-white shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-black uppercase tracking-wider">
                    SaaS Setup Required
                  </span>
                  <span className="text-xs text-slate-300 font-mono">Status: Awaiting Account Linking</span>
                </div>
                <h3 className="text-base font-black text-white">No Cloud Accounts Connected</h3>
                <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
                  Enter your Primary and Secondary Snowflake credentials to initiate continuous cross-cloud telemetry, automatic WAN replication, and zero-touch failover protection.
                </p>
              </div>
              <button
                onClick={() => setShowOnboarding(true)}
                className="px-4 py-2.5 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white rounded-lg text-xs font-black shadow-md transition flex items-center space-x-2 cursor-pointer shrink-0"
              >
                <Zap className="w-4 h-4 text-amber-300" />
                <span>Link Primary & Secondary Accounts</span>
              </button>
            </div>
          )}

          {/* Toast Banner when accounts are linked and ready */}
          {readyToast && (
            <div className="bg-emerald-600 text-white px-5 py-3 rounded-xl shadow-lg flex items-center justify-between">
              <div className="flex items-center space-x-2.5 text-xs font-bold">
                <span>{readyToast}</span>
              </div>
              <button onClick={() => setReadyToast(null)} className="text-emerald-100 hover:text-white font-black text-sm cursor-pointer">
                ✕
              </button>
            </div>
          )}

          {/* ============================================================== */}
          {/* SECTION 1: Live Snowflake KPIs                                 */}
          {/* ============================================================== */}
          <div>
            <div className="section-tag mb-3 flex items-center justify-between">
              <span>Live Snowflake Telemetry (Cloud Services Metadata — 0 Idle Compute Burn)</span>
              <span className="text-[11px] text-slate-500 font-mono">
                {status?.last_probe_at ? `Last Snowflake response: ${status.last_probe_at}` : '--'}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
              {kpis.length === 0
                ? Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="enterprise-card p-4 animate-pulse">
                      <div className="h-3 w-24 bg-slate-200 rounded mb-3" />
                      <div className="h-7 w-32 bg-slate-200 rounded mb-2" />
                      <div className="h-3 w-full bg-slate-100 rounded" />
                    </div>
                  ))
                : kpis.map((kpi) => (
                    <div key={kpi.id} className="enterprise-card p-4 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{kpi.title}</span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            kpi.status === 'healthy' || kpi.status === 'success'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : kpi.status === 'info'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : 'bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                        >
                          {kpi.badge}
                        </span>
                      </div>
                      <div>
                        <div className="text-xl font-black text-slate-900 tracking-tight tabular-nums mb-1">{kpi.value}</div>
                        <div className="text-[11px] text-slate-500 font-medium line-clamp-1">{kpi.subtext}</div>
                      </div>
                      <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] font-mono text-slate-500 flex items-center justify-between">
                        <span className="truncate">{kpi.trend}</span>
                        <Activity className="w-3.5 h-3.5 text-emerald-500 shrink-0 ml-1" />
                      </div>
                    </div>
                  ))}
            </div>
          </div>

          {/* ============================================================== */}
          {/* SECTION 2: Multi-Cloud Topology Cards & Live RTT Stream       */}
          {/* ============================================================== */}
          <div>
            <div className="section-tag mb-3 flex items-center justify-between">
              <span>Multi-Cloud Snowflake Topology (Active Leader vs Standby Replica)</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Primary Live Card */}
              <div
                className={`enterprise-card p-5 border-t-4 ${
                  awsSnap?.fg_is_primary ? 'border-t-emerald-500 bg-emerald-50/15' : 'border-t-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                      {status?.is_configured ? `${awsSnap?.cloud || 'Primary Cloud'} · ${awsSnap?.region || 'us-east-1'}` : 'Primary Cloud · --'}
                    </span>
                    <h3 className="text-base font-black text-slate-900 mt-1">
                      {status?.is_configured ? `${awsSnap?.account_name || 'PRIMARY_ACCOUNT'} (${awsSnap?.locator || '--'})` : 'Primary Cloud Account (--)'}
                    </h3>
                  </div>
                  <span
                    className={`text-[11px] font-black px-2.5 py-1 rounded-md border ${
                      awsSnap?.fg_is_primary
                        ? 'bg-emerald-600 text-white border-emerald-700'
                        : 'bg-slate-100 text-slate-700 border-slate-300'
                    }`}
                  >
                    {status?.is_configured ? (awsSnap?.fg_is_primary ? 'PRIMARY (READ-WRITE)' : 'REPLICA (READ-ONLY)') : 'UNCONFIGURED'}
                  </span>
                </div>

                <div className="space-y-2 text-xs mt-4 pt-3 border-t border-slate-200/80">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Client Redirect DNS:</span>
                    <strong className={awsSnap?.conn_is_primary ? 'text-emerald-700' : 'text-slate-500'}>
                      {status?.is_configured ? (awsSnap?.conn_is_primary ? '100% ACTIVE TRAFFIC LEADER' : '0% STANDBY') : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">
                      {awsSnap?.row_count > 0 ? 'FINANCIAL_TRANSACTIONS:' : 'Hosted Database Rows:'}
                    </span>
                    <strong className="text-slate-900 font-mono tabular-nums">
                      {status?.is_configured && awsSnap?.row_count != null ? `${awsSnap.row_count.toLocaleString()} rows` : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Live SQL Probe Latency:</span>
                    <strong className="text-slate-800 font-mono">
                      {awsSnap?.ping_ms != null ? `${awsSnap.ping_ms} ms` : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Resource Monitor Credits:</span>
                    <strong className="text-slate-800 font-mono">
                      {status?.is_configured && awsSnap?.used_credits != null ? `${awsSnap.used_credits.toFixed(2)} / ${awsSnap.credit_quota} Cr` : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400 font-mono pt-1">
                    <span>Last Query ID:</span>
                    <span className="truncate max-w-[180px]">{awsSnap?.last_sfqid || '--'}</span>
                  </div>
                </div>
              </div>

              {/* Standby Live Card */}
              <div
                className={`enterprise-card p-5 border-t-4 ${
                  azSnap?.fg_is_primary ? 'border-t-emerald-500 bg-emerald-50/15' : 'border-t-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider text-sky-700 bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                      {status?.is_configured ? `${azSnap?.cloud || 'Standby Cloud'} · ${azSnap?.region || 'East US 2'}` : 'Secondary Cloud · --'}
                    </span>
                    <h3 className="text-base font-black text-slate-900 mt-1">
                      {status?.is_configured ? `${azSnap?.account_name || 'SECONDARY_ACCOUNT'} (${azSnap?.locator || '--'})` : 'Secondary Cloud Account (--)'}
                    </h3>
                  </div>
                  <span
                    className={`text-[11px] font-black px-2.5 py-1 rounded-md border ${
                      azSnap?.fg_is_primary
                        ? 'bg-emerald-600 text-white border-emerald-700'
                        : 'bg-slate-100 text-slate-700 border-slate-300'
                    }`}
                  >
                    {status?.is_configured ? (azSnap?.fg_is_primary ? 'PRIMARY (READ-WRITE)' : 'REPLICA (READ-ONLY)') : 'UNCONFIGURED'}
                  </span>
                </div>

                <div className="space-y-2 text-xs mt-4 pt-3 border-t border-slate-200/80">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Client Redirect DNS:</span>
                    <strong className={azSnap?.conn_is_primary ? 'text-emerald-700' : 'text-slate-500'}>
                      {status?.is_configured ? (azSnap?.conn_is_primary ? '100% ACTIVE TRAFFIC LEADER' : '0% STANDBY') : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">
                      {azSnap?.row_count > 0 ? 'FINANCIAL_TRANSACTIONS:' : 'Replicated Database Rows:'}
                    </span>
                    <strong className="text-slate-900 font-mono tabular-nums">
                      {status?.is_configured && azSnap?.row_count != null ? `${azSnap.row_count.toLocaleString()} rows` : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Live SQL Probe Latency:</span>
                    <strong className="text-slate-800 font-mono">
                      {azSnap?.ping_ms != null ? `${azSnap.ping_ms} ms` : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Resource Monitor Credits:</span>
                    <strong className="text-slate-800 font-mono">
                      {status?.is_configured && azSnap?.used_credits != null ? `${azSnap.used_credits.toFixed(2)} / ${azSnap.credit_quota} Cr` : '--'}
                    </strong>
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-400 font-mono pt-1">
                    <span>Last Query ID:</span>
                    <span className="truncate max-w-[180px]">{azSnap?.last_sfqid || '--'}</span>
                  </div>
                </div>
              </div>

              {/* Dynamic Live Probe RTT Chart */}
              <div className="enterprise-card p-5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-black text-slate-900">Live SQL RTT Stream ({timeline.length} samples)</h3>
                    <span className="text-[10px] font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                      Real-Time Chart
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mb-3">
                    Measured Snowflake round-trip query latency on every 5s probe cycle.
                  </p>

                  <div className="h-28 w-full bg-slate-50 rounded-lg border border-slate-200 p-2 relative">
                    {timeline.length === 0 ? (
                      <div className="h-full flex items-center justify-center text-xs text-slate-400">
                        {status?.is_configured ? 'Collecting first live probe sample...' : 'Standby mode (--)'}
                      </div>
                    ) : (
                      <svg className="w-full h-full overflow-visible" viewBox="0 0 300 80" preserveAspectRatio="none">
                        <polyline
                          points={buildPolyline('aws_ping_ms')}
                          fill="none"
                          stroke="#F59E0B"
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                        <polyline
                          points={buildPolyline('azure_ping_ms')}
                          fill="none"
                          stroke="#0EA5E9"
                          strokeWidth="2"
                          strokeLinecap="round"
                        />
                      </svg>
                    )}
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-500 mt-2 font-semibold">
                    <span className="text-amber-600">● Primary RTT: {status?.is_configured ? (awsSnap?.ping_ms ?? '--') : '--'} ms</span>
                    <span className="text-sky-600">● Secondary RTT: {status?.is_configured ? (azSnap?.ping_ms ?? '--') : '--'} ms</span>
                  </div>
                </div>

                <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-slate-700">
                  <span>Replication Schedule:</span>
                  <span className="text-emerald-700 font-mono">
                    {status?.is_configured ? (diagnostics?.data_health?.schedule || '10 MINUTE') : '--'}
                  </span>
                </div>
              </div>
            </div>

            {/* Health Probes Availability Bar Strip */}
            <div className="mt-4 w-full">
              <div className="enterprise-card p-5 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-black text-slate-900 flex items-center space-x-1.5">
                    <Activity className="w-4 h-4 text-indigo-600" />
                    <span>Live Health Probe Availability & 3-Strike Telemetry</span>
                  </h3>
                  <span className="text-[10px] font-bold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded border border-indigo-200 font-mono">
                    Uptime: {status?.is_configured ? `${diagnostics?.probe_metadata?.uptime_seconds ?? 0}s` : '--'}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mb-3">
                  Real-time per-probe health pulses across the latest probe cycles.
                </p>

                <div className="space-y-2.5 bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <div>
                    <div className="flex justify-between text-[11px] font-bold mb-1">
                      <span className="text-slate-700">
                        {status?.is_configured ? `${awsSnap?.cloud || 'Primary'} (${awsSnap?.region || 'us-east-1'}) Probe Availability` : 'Primary Cloud Probe Availability (--)'}
                      </span>
                      <span className="text-amber-700 font-mono">
                        {status?.is_configured ? `${diagnostics?.probe_metadata?.aws_uptime_pct ?? 100}%` : '--'}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1 h-4">
                      {timeline.length === 0 ? (
                        <span className="text-[10px] text-slate-400">Sampling...</span>
                      ) : (
                        timeline.map((pt, i) => (
                          <div
                            key={i}
                            title={`${pt.time} — Primary ${pt.aws_healthy === 0 ? 'FAILED (Strike)' : `${pt.aws_ping_ms}ms`}`}
                            className={`flex-1 h-full rounded-xs transition-all ${
                              pt.aws_healthy === 0 ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'
                            }`}
                          />
                        ))
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[11px] font-bold mb-1">
                      <span className="text-slate-700">
                        {status?.is_configured ? `${azSnap?.cloud || 'Secondary'} (${azSnap?.region || 'East US 2'}) Probe Availability` : 'Secondary Cloud Probe Availability (--)'}
                      </span>
                      <span className="text-sky-700 font-mono">
                        {status?.is_configured ? `${diagnostics?.probe_metadata?.azure_uptime_pct ?? 100}%` : '--'}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1 h-4">
                      {timeline.length === 0 ? (
                        <span className="text-[10px] text-slate-400">Sampling...</span>
                      ) : (
                        timeline.map((pt, i) => (
                          <div
                            key={i}
                            title={`${pt.time} — Secondary ${pt.azure_healthy === 0 ? 'FAILED' : `${pt.azure_ping_ms}ms`}`}
                            className={`flex-1 h-full rounded-xs transition-all ${
                              pt.azure_healthy === 0 ? 'bg-red-500' : 'bg-sky-500'
                            }`}
                          />
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ============================================================== */}
          {/* SECTION 3: Full-Stack Microservice Workload Hydration Matrix   */}
          {/* ============================================================== */}
          <WorkloadHydrationMatrix />

          {/* ============================================================== */}
          {/* SECTION 4: Live PaySim Transaction Ingestion Stream */}
          {/* ============================================================== */}
          <LiveTransactionStream />

          {/* ============================================================== */}
          {/* SECTION 5: GitHub Actions Style Live Workflow & SQL Stream     */}
          {/* ============================================================== */}
          <LiveExecutionConsole
            consoleRef={consoleRef}
            consoleTab={consoleTab}
            setConsoleTab={setConsoleTab}
            workflowRun={workflowRun}
            liveLogs={liveLogs}
            toggleStepExpand={toggleStepExpand}
          />

          {/* ============================================================== */}
          {/* SECTION 6: Emergency Disaster Operations Room (Failover/Back) */}
          {/* ============================================================== */}
          <div>
            <div className="section-tag mb-3 flex items-center justify-between">
              <span>Live Snowflake DR Operations (Executes Real Cross-Cloud DDL)</span>
              <span className="text-[11px] text-slate-500 font-medium">
                Streams live SQL & Query IDs into the GitHub Actions Console above
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="enterprise-card p-5 border-l-4 border-l-amber-500 flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-black text-slate-900 flex items-center space-x-1.5 mb-2">
                    <ArrowRightLeft className="w-4 h-4 text-amber-500" />
                    <span>Emergency Failover to Standby ({status?.is_configured ? (azSnap?.locator || '--') : '--'})</span>
                  </h3>
                  <p className="text-xs text-slate-600 mb-4">
                    Runs real <code className="font-mono">ALTER FAILOVER GROUP PRIMARY</code> + <code className="font-mono">ALTER CONNECTION PRIMARY</code> on Secondary account.
                  </p>
                </div>
                <button
                  disabled={isWorkflowBusy || !status?.is_configured}
                  onClick={() => startLiveWorkflow('failover')}
                  className="w-full py-2.5 px-4 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white font-bold text-xs rounded-lg shadow-xs transition flex items-center justify-center space-x-2 cursor-pointer"
                >
                  <ArrowRightLeft className="w-4 h-4" />
                  <span>Promote Standby to PRIMARY (Live)</span>
                </button>
              </div>

              <div className="enterprise-card p-5 border-l-4 border-l-blue-500 flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-black text-slate-900 flex items-center space-x-1.5 mb-2">
                    <RotateCcw className="w-4 h-4 text-blue-500" />
                    <span>Delta Catch-Up & Failback to Primary ({status?.is_configured ? (awsSnap?.locator || '--') : '--'})</span>
                  </h3>
                  <p className="text-xs text-slate-600 mb-4">
                    Refreshes reverse delta onto Primary account, restores Primary authority, and flips Anycast DNS back.
                  </p>
                </div>
                <button
                  disabled={isWorkflowBusy || !status?.is_configured}
                  onClick={() => startLiveWorkflow('failback')}
                  className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs rounded-lg shadow-xs transition flex items-center justify-center space-x-2 cursor-pointer"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Restore Primary to PRIMARY (Live)</span>
                </button>
              </div>
            </div>
          </div>

          {/* ============================================================== */}
          {/* SECTION 7: Multi-Cloud Infrastructure & Object Ledger Table    */}
          {/* ============================================================== */}
          <ObjectLedgerTable
            ledger={ledger}
            tableSearch={tableSearch}
            setTableSearch={setTableSearch}
          />

          {/* ============================================================== */}
          {/* SECTION 8: Real Session Execution History Log                  */}
          {/* ============================================================== */}
          <div>
            <div className="section-tag mb-3 flex items-center justify-between">
              <span>Live Session Execution History (Real Runs Only)</span>
              <span className="text-[11px] text-slate-400 font-medium">{drillHistory.length} runs in this session</span>
            </div>

            <div className="enterprise-card overflow-hidden">
              {drillHistory.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500">
                  No operations executed yet in this session — zero pre-populated fake rows. Run any action above to record real measured RTO/RPO runs!
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50/50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        <th className="py-2.5 px-4">Run ID</th>
                        <th className="py-2.5 px-4">Timestamp (UTC)</th>
                        <th className="py-2.5 px-4">Operation</th>
                        <th className="py-2.5 px-4">Cloud Route</th>
                        <th className="py-2.5 px-4">Measured Time</th>
                        <th className="py-2.5 px-4">Snowflake Rows</th>
                        <th className="py-2.5 px-4">Delta (RPO)</th>
                        <th className="py-2.5 px-4">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {drillHistory.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-50/70 transition">
                          <td className="py-3 px-4 font-mono font-bold text-slate-800">{item.id}</td>
                          <td className="py-3 px-4 text-slate-600 font-mono">{item.timestamp}</td>
                          <td className="py-3 px-4 font-bold text-slate-900">{item.operation}</td>
                          <td className="py-3 px-4 text-slate-700">{item.route}</td>
                          <td className="py-3 px-4 font-black text-blue-700 font-mono">{item.duration}</td>
                          <td className="py-3 px-4 text-slate-700 font-mono">{item.rows}</td>
                          <td className="py-3 px-4 font-black text-emerald-600">{item.rpo}</td>
                          <td className="py-3 px-4">
                            <span className="text-[10px] font-black px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
                              {item.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Account Onboarding Modal */}
      <OnboardingModal
        isOpen={showOnboarding}
        onClose={() => setShowOnboarding(false)}
        onSuccess={() => {
          setShowOnboarding(false);
          setReadyToast('🎉 Ready to Migrate & Protect! Primary and Secondary accounts linked, Anycast connection primed, and replication active.');
          fetchTelemetry();
        }}
        initialStatus={status}
      />
    </div>
  );
}
