/**
 * GitHub Actions-Style Live Execution Stream & Real-Time SQL Runner
 *
 * Provides real-time expandable workflow step visualization, stopwatch timer,
 * and live background Snowflake SQL stream.
 */

import React from 'react';
import {
  Clock,
  CheckCircle2,
  Loader2,
  XCircle,
  Circle,
  Play,
  ChevronDown,
  ChevronRight,
  Terminal,
} from 'lucide-react';

export default function LiveExecutionConsole({
  consoleRef,
  consoleTab,
  setConsoleTab,
  workflowRun,
  liveLogs,
  toggleStepExpand,
}) {
  return (
    <div ref={consoleRef} className="mb-6">
      <div className="section-tag mb-2.5 flex items-center justify-between">
        <span className="flex items-center space-x-1.5">
          <Terminal className="w-3.5 h-3.5 text-slate-700" />
          <span>Live Execution Stream (GitHub Actions Real-Time SQL Runner)</span>
        </span>
      </div>

      <div className="rounded-xl overflow-hidden border border-slate-800 bg-[#0D1117] text-slate-200 shadow-lg">
        {/* Dark Console Top Bar */}
        <div className="px-4 py-3 bg-[#161B22] border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setConsoleTab('workflow')}
              className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center space-x-1.5 transition cursor-pointer ${
                consoleTab === 'workflow'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {workflowRun.state === 'running' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-300" />
              ) : workflowRun.state === 'success' ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : workflowRun.state === 'error' ? (
                <XCircle className="w-3.5 h-3.5 text-red-400" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              <span>Workflow Steps {workflowRun.runId ? `(${workflowRun.runId})` : ''}</span>
            </button>

            <button
              onClick={() => setConsoleTab('probes')}
              className={`px-3 py-1.5 rounded-md text-xs font-bold flex items-center space-x-1.5 transition cursor-pointer ${
                consoleTab === 'probes'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Live Background SQL Stream ({liveLogs.length})</span>
            </button>
          </div>

          {/* Live Real Stopwatch (Only ticks during active workflow) */}
          <div className="flex items-center space-x-3">
            {workflowRun.state !== 'idle' && (
              <div className="flex items-center space-x-2 bg-[#0D1117] px-3 py-1 rounded-md border border-slate-700 font-mono text-xs">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-bold text-white tabular-nums">{workflowRun.elapsedS}s</span>
                <span
                  className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                    workflowRun.state === 'running'
                      ? 'bg-amber-500/20 text-amber-300'
                      : workflowRun.state === 'success'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-red-500/20 text-red-300'
                  }`}
                >
                  {workflowRun.state}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* TAB 1: GitHub Actions Expandable Step-by-Step Runner */}
        {consoleTab === 'workflow' ? (
          <div className="p-4 space-y-2 max-h-[460px] overflow-y-auto">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800/80">
              <div className="text-xs font-bold text-slate-200">{workflowRun.title}</div>
            </div>

            {workflowRun.steps.length === 0 ? (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-[#161B22] border border-slate-800 flex items-center justify-between gap-3">
                  <div className="text-xs text-slate-300">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse mr-2" />
                    <strong>Live Snowflake Stream Active</strong> — Real-time background SQL execution stream. Trigger Failover or Failback in the sidebar to stream expandable execution steps live:
                  </div>
                </div>

                <div className="rounded-lg border border-slate-800 bg-[#010409] p-3 font-mono text-[11px] space-y-1.5 max-h-[320px] overflow-y-auto">
                  {liveLogs.length === 0 ? (
                    <div className="text-slate-500 flex items-center space-x-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                      <span>Opening RSA-2048 JWT session to Snowflake AWS & Azure...</span>
                    </div>
                  ) : (
                    liveLogs.slice(0, 20).map((lg, i) => (
                      <div key={i} className="leading-relaxed border-b border-slate-900/80 pb-1">
                        <div className="flex flex-wrap items-baseline gap-x-2">
                          <span className="text-slate-500">{lg.ts}</span>
                          <span className="px-1.5 rounded bg-slate-800 text-cyan-300 text-[10px]">{lg.account}</span>
                          <span
                            className={
                              lg.level === 'ERROR'
                                ? 'text-red-400 font-bold'
                                : lg.level === 'SUCCESS'
                                ? 'text-emerald-300'
                                : 'text-slate-200'
                            }
                          >
                            {lg.message}
                          </span>
                          {lg.sfqid && <span className="text-purple-400 text-[10px]">[sfqid={lg.sfqid}]</span>}
                        </div>
                        {lg.sql && (
                          <div className="pl-16 text-blue-300/80 text-[10px] truncate">
                            SQL&gt; {lg.sql}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : (
              workflowRun.steps.map((step, idx) => (
                <div key={idx} className="rounded-lg border border-slate-800 bg-[#161B22]/70 overflow-hidden">
                  <button
                    onClick={() => toggleStepExpand(idx)}
                    className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-slate-800/50 transition cursor-pointer"
                  >
                    <div className="flex items-center space-x-2.5 min-w-0">
                      {step.expanded ? (
                        <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      )}
                      {step.status === 'done' ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      ) : step.status === 'running' ? (
                        <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
                      ) : step.status === 'error' ? (
                        <XCircle className="w-4 h-4 text-red-400 shrink-0" />
                      ) : (
                        <Circle className="w-4 h-4 text-slate-600 shrink-0" />
                      )}
                      <span
                        className={`text-xs truncate ${
                          step.status === 'running'
                            ? 'text-white font-bold'
                            : step.status === 'done'
                            ? 'text-slate-200 font-semibold'
                            : 'text-slate-500'
                        }`}
                      >
                        {step.name}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 text-[11px] font-mono shrink-0 ml-2">
                      {step.durationS != null && (
                        <span className="text-slate-400">{step.durationS}s</span>
                      )}
                    </div>
                  </button>
                  {step.expanded && (
                    <div className="px-4 py-3 bg-[#010409] border-t border-slate-800 font-mono text-[11px] space-y-1">
                      {step.logs.length === 0 ? (
                        <div className="text-slate-600 italic">No output logged for this step</div>
                      ) : (
                        step.logs.map((lg, logIdx) => (
                          <div key={logIdx} className="leading-relaxed">
                            <span className="text-slate-500 mr-2">{lg.ts}</span>
                            <span
                              className={
                                lg.level === 'ERROR'
                                ? 'text-red-400 font-bold'
                                : lg.level === 'SUCCESS'
                                ? 'text-emerald-300 font-bold'
                                : lg.level === 'WARN'
                                ? 'text-amber-300'
                                : 'text-slate-300'
                              }
                            >
                              {lg.message}
                            </span>
                            {lg.sql && (
                              <div className="pl-16 text-blue-300/80 text-[10px] truncate">
                                SQL&gt; {lg.sql}
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          /* TAB 2: Live Real-Time SQL Probe Stream */
          <div className="p-3 bg-[#010409] font-mono text-[11px] space-y-1.5 max-h-[460px] overflow-y-auto">
            {liveLogs.length === 0 ? (
              <div className="text-slate-500 text-center py-6">Connecting to live SQL telemetry stream...</div>
            ) : (
              liveLogs.map((lg, i) => (
                <div key={i} className="leading-relaxed border-b border-slate-900/60 pb-1">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-slate-500">{lg.ts}</span>
                    <span className="px-1.5 rounded bg-slate-800 text-cyan-300 text-[10px]">{lg.account}</span>
                    <span
                      className={
                        lg.level === 'ERROR'
                          ? 'text-red-400 font-bold'
                          : lg.level === 'SUCCESS'
                          ? 'text-emerald-300'
                          : 'text-slate-200'
                      }
                    >
                      {lg.message}
                    </span>
                    {lg.sfqid && <span className="text-purple-400 text-[10px]">[sfqid={lg.sfqid}]</span>}
                  </div>
                  {lg.sql && (
                    <div className="pl-16 text-blue-300/80 text-[10px] truncate">
                      SQL&gt; {lg.sql}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

