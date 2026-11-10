/**
 * Enterprise DR Control Plane — Multi-Cloud Sidebar Navigation
 *
 * Displays live cloud account connectivity, Anycast DNS routing status,
 * 3-strike autonomous watchdog sentry, and credit guardrails.
 */

import React from 'react';
import { Shield, Network, Copy, Check, AlertCircle } from 'lucide-react';

export default function Sidebar({
  apiOnline,
  status,
  awsSnap,
  azSnap,
  anycastSnap,
  totalCreditsUsed,
  totalCreditQuota,
  creditPct,
  copiedHandle,
  copyHandle,
}) {
  const isConfigured = Boolean(status?.is_configured);

  return (
    <aside className="w-full md:w-72 bg-white border-r border-slate-200 flex flex-col justify-between shrink-0 p-5 shadow-xs">
      <div className="space-y-5">
        {/* Branding & Mission Control Title */}
        <div className="flex items-center space-x-3 pb-4 border-b border-slate-100">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-black text-slate-900 leading-tight">Auto Fail-Over</h2>
            <p className="text-[11px] text-slate-500 font-medium">Autonomous Cloud Resiliency</p>
          </div>
        </div>

        {/* Live Multi-Cloud Account Status */}
        <div>
          <div className="section-tag mb-2.5 flex items-center justify-between">
            <span>Live Snowflake Accounts</span>
            <span
              className={`w-2 h-2 rounded-full ${
                apiOnline && status?.status === 'HEALTHY'
                  ? 'bg-emerald-500 animate-pulse'
                  : 'bg-amber-500'
              }`}
            />
          </div>
          <div className="space-y-2">
            {/* Primary Cloud Account Badge */}
            <div className="p-2.5 rounded-lg border border-slate-200 bg-slate-50/70">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      awsSnap?.healthy ? 'bg-emerald-500' : 'bg-slate-300'
                    }`}
                  />
                  <span className="text-xs font-bold text-slate-800">
                    {isConfigured ? `${awsSnap?.cloud || 'AWS'} ${awsSnap?.region || 'us-east-1'}` : 'Primary Cloud (--)'}
                  </span>
                </div>
                <span className="text-[10px] font-mono font-bold text-slate-600 bg-white px-1.5 py-0.5 rounded border border-slate-200">
                  {awsSnap?.locator && awsSnap.locator !== '--' ? awsSnap.locator : '--'}
                </span>
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-slate-500">
                <span>
                  {isConfigured
                    ? awsSnap?.fg_is_primary
                      ? '🟢 PRIMARY (R/W)'
                      : '🔵 REPLICA (R/O)'
                    : '--'}
                </span>
                <span>{awsSnap?.ping_ms != null ? `${awsSnap.ping_ms} ms` : '--'}</span>
              </div>
            </div>

            {/* Standby Cloud Account Badge */}
            <div className="p-2.5 rounded-lg border border-slate-200 bg-slate-50/70">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      azSnap?.healthy ? 'bg-emerald-500' : 'bg-slate-300'
                    }`}
                  />
                  <span className="text-xs font-bold text-slate-800">
                    {isConfigured ? `${azSnap?.cloud || 'Azure'} ${azSnap?.region || 'East US 2'}` : 'Secondary Cloud (--)'}
                  </span>
                </div>
                <span className="text-[10px] font-mono font-bold text-slate-600 bg-white px-1.5 py-0.5 rounded border border-slate-200">
                  {azSnap?.locator && azSnap.locator !== '--' ? azSnap.locator : '--'}
                </span>
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-slate-500">
                <span>
                  {isConfigured
                    ? azSnap?.fg_is_primary
                      ? '🟢 PRIMARY (R/W)'
                      : '🔵 REPLICA (R/O)'
                    : '--'}
                </span>
                <span>{azSnap?.ping_ms != null ? `${azSnap.ping_ms} ms` : '--'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Global Client Redirect Anycast Endpoint Handle */}
        <div className="enterprise-card p-3.5 bg-slate-50/50">
          <div className="section-tag mb-1.5 flex items-center justify-between">
            <span>Global Anycast DNS</span>
            <Network className="w-3.5 h-3.5 text-blue-600" />
          </div>
          <div className="p-2 bg-white rounded border border-slate-200 text-[11px] font-mono break-all text-slate-700 select-all mb-2">
            {isConfigured ? status?.global_redirect_handle || '--' : '--'}
          </div>
          <div className="text-[10px] text-slate-600 mb-2 flex items-center justify-between">
            <span>Resolved Target:</span>
            <strong className="text-blue-700 font-mono">
              {isConfigured && anycastSnap?.landed_locator
                ? `${anycastSnap.landed_locator} (${anycastSnap.landed_region})`
                : '--'}
            </strong>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <button
              onClick={copyHandle}
              className="flex items-center justify-center space-x-1 py-1.5 px-2 bg-white hover:bg-slate-100 border border-slate-200 rounded text-[11px] font-bold text-slate-700 transition cursor-pointer"
            >
              {copiedHandle ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3 text-slate-500" />}
              <span>{copiedHandle ? 'Copied' : 'Copy URL'}</span>
            </button>
            <div className="flex items-center justify-center text-[10px] font-mono text-slate-500 bg-white border border-slate-200 rounded px-1">
              {anycastSnap?.latency_ms != null ? `${anycastSnap.latency_ms}ms` : '--'}
            </div>
          </div>
        </div>

        {/* Autonomous 3-Strike Watchdog Sentry Controls */}
        <div className="enterprise-card p-3.5 bg-indigo-50/40 border-indigo-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-black text-indigo-950 uppercase tracking-tight flex items-center space-x-1">
              <Shield className="w-3.5 h-3.5 text-indigo-600" />
              <span>Watchdog Sentry</span>
            </span>
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                status?.watchdog?.enabled
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-amber-100 text-amber-800'
              }`}
            >
              {status?.watchdog?.enabled ? 'AUTO-FAILOVER ON' : 'MANUAL MODE'}
            </span>
          </div>

          {/* 3-Strike Visual Indicator */}
          <div className="flex items-center justify-between bg-white p-2 rounded border border-slate-200 mb-2">
            <span className="text-[11px] font-bold text-slate-700">Primary Failed Strikes:</span>
            <div className="flex items-center space-x-1.5">
              {[1, 2, 3].map((s) => {
                const activeStrike = (status?.watchdog?.consecutive_failures || 0) >= s;
                return (
                  <span
                    key={s}
                    className={`w-5 h-5 rounded-full text-[10px] font-black flex items-center justify-center border ${
                      activeStrike
                        ? 'bg-red-600 text-white border-red-700 animate-bounce'
                        : 'bg-slate-100 text-slate-400 border-slate-200'
                    }`}
                  >
                    {s}
                  </span>
                );
              })}
            </div>
          </div>

          <div className="text-[11px] text-indigo-900/80 font-semibold flex items-center justify-between">
            <span>Watchdog Mode:</span>
            <span className="font-bold text-indigo-700">Autonomous (Active)</span>
          </div>
        </div>
      </div>

      {/* Live FinOps Resource Monitor & Credit Guard Footer */}
      <div className="pt-4 mt-6 border-t border-slate-100 text-[11px] text-slate-500 shrink-0">
        <div className="flex flex-wrap justify-between items-center gap-1 mb-1.5">
          <span className="font-bold text-slate-700 text-[10px] uppercase tracking-wider">DR_CREDIT_GUARD</span>
          <span className="font-bold px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200">
            60s Auto-Suspend
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div className="bg-emerald-500 h-full transition-all duration-500" style={{ width: `${creditPct}%` }} />
        </div>
        <div className="flex justify-between text-[10px] text-slate-400 mt-1.5 tabular-nums">
          <span>Used: {totalCreditsUsed} Cr</span>
          <span>Quota: {totalCreditQuota} Cr</span>
        </div>
      </div>
    </aside>
  );
}

