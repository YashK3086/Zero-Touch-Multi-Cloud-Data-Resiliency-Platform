/**
 * Enterprise DR Control Plane — Executive Dashboard Header Bar
 *
 * Displays git probe metadata, instant audit PDF generation button,
 * multi-cloud onboarding modal launcher, and connection status pill.
 */

import React from 'react';
import { Download, Database, Loader2 } from 'lucide-react';

export default function DashboardHeader({
  status,
  downloadingPdf,
  handleDownloadPdfReport,
  setShowOnboarding,
}) {
  const isConfigured = Boolean(status?.is_configured);

  return (
    <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-20 shadow-2xs">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-slate-500 font-semibold mb-1">
            <span>Live Snowflake Telemetry</span>
            <span>/</span>
            <span className="text-blue-600 font-bold">
              Probe #{status?.probe_count ?? 0} · Commit {status?.git?.commit || 'HEAD'} ({status?.git?.branch || 'main'})
            </span>
          </div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 tracking-tight">
            Auto Fail-Over
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Executive Audit PDF Export Button */}
          <button
            onClick={handleDownloadPdfReport}
            disabled={downloadingPdf}
            className="flex items-center space-x-1.5 bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 px-3 py-1.5 rounded-lg text-xs font-bold shadow-xs transition cursor-pointer"
            title="Download Executive DR Compliance Certificate & Audit for Latest 5 Migrations"
          >
            {downloadingPdf ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
            ) : (
              <Download className="w-3.5 h-3.5 text-blue-600" />
            )}
            <span>📄 Export Audit PDF</span>
          </button>

          {/* Account Onboarding Modal Launcher */}
          <button
            onClick={() => setShowOnboarding(true)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold shadow-xs transition cursor-pointer ${
              isConfigured
                ? 'bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300'
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white animate-pulse'
            }`}
            title="Configure Primary & Secondary Snowflake Accounts"
          >
            <Database className="w-3.5 h-3.5" />
            <span>{isConfigured ? '🔗 Manage Accounts' : '⚡ Connect Accounts'}</span>
          </button>

          {/* Live Telemetry Heartbeat Status Pill */}
          <div className="flex items-center space-x-2 bg-emerald-50 text-emerald-800 border border-emerald-200 px-3 py-1.5 rounded-lg text-xs font-bold shadow-2xs">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>{isConfigured ? 'Live Telemetry Active (2.5s)' : 'Standby Mode'}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

