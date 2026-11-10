/**
 * Multi-Cloud Infrastructure & Snowflake Object Inventory Ledger
 *
 * Renders real-time discovered AWS S3 buckets, EC2 workloads,
 * Snowflake databases, Failover Groups, and Anycast routing endpoints.
 */

import React from 'react';
import { Search, Database, Cloud } from 'lucide-react';

export default function ObjectLedgerTable({ ledger, tableSearch, setTableSearch }) {
  const filteredLedger = ledger.filter(
    (item) =>
      item.name?.toLowerCase().includes(tableSearch.toLowerCase()) ||
      item.provider?.toLowerCase().includes(tableSearch.toLowerCase()) ||
      item.target?.toLowerCase().includes(tableSearch.toLowerCase())
  );

  return (
    <div className="mb-6">
      <div className="section-tag mb-3 flex items-center justify-between">
        <span>Live Multi-Cloud Infrastructure & Snowflake Object Ledger</span>
        <span className="text-[11px] text-slate-400 font-medium">{ledger.length} live objects</span>
      </div>

      <div className="enterprise-card overflow-hidden">
        {/* Search Bar */}
        <div className="p-3 bg-slate-50/70 border-b border-slate-200 flex items-center justify-between gap-3">
          <div className="relative w-full max-w-sm">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Filter live objects by name, cloud, or target..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-slate-700 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Ledger Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="py-2.5 px-4">Cloud / Snowflake Object</th>
                <th className="py-2.5 px-4">Cloud Provider & Region</th>
                <th className="py-2.5 px-4">Target Identifier / Endpoint</th>
                <th className="py-2.5 px-4">Live State / Volume</th>
                <th className="py-2.5 px-4">Lifecycle / Authority</th>
                <th className="py-2.5 px-4">Last Query ID (sfqid)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {filteredLedger.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50/70 transition">
                  <td className="py-3 px-4 font-bold text-slate-900 flex items-center space-x-2">
                    <Database className="w-4 h-4 text-blue-600 shrink-0" />
                    <span>{row.name}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        row.provider === 'AWS'
                          ? 'bg-amber-50 text-amber-800 border-amber-200'
                          : row.provider === 'Azure'
                          ? 'bg-sky-50 text-sky-800 border-sky-200'
                          : 'bg-purple-50 text-purple-800 border-purple-200'
                      }`}
                    >
                      {row.provider} · {row.region}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600 font-mono text-[11px]">{row.target}</td>
                  <td className="py-3 px-4 font-bold text-slate-800 tabular-nums">{row.volume}</td>
                  <td className="py-3 px-4 font-semibold text-slate-700">{row.lifecycle}</td>
                  <td className="py-3 px-4 font-mono text-[10px] text-slate-500">{row.sfqid || '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

