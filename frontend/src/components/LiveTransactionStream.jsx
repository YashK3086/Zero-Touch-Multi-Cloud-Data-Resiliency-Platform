import React, { useState, useEffect } from 'react';
import { Activity, ArrowUpRight, ShieldAlert, ShieldCheck, Zap, Database } from 'lucide-react';

export default function LiveTransactionStream() {
  const [streamData, setStreamData] = useState(null);

  const fetchStream = async () => {
    try {
      const res = await fetch('/api/transactions/stream');
      if (res.ok) {
        const data = await res.json();
        setStreamData(data);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchStream();
    const interval = setInterval(fetchStream, 2500);
    return () => clearInterval(interval);
  }, []);

  const isConnected = streamData?.connected;
  const activeCloud = streamData?.active_cloud || '--';
  const isAzure = activeCloud.toUpperCase() === 'AZURE';
  const transactions = streamData?.transactions || [];
  const totalRows = streamData?.total_rows;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs mb-6">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 shadow-xs">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-black text-slate-900 tracking-tight uppercase">
                {totalRows > 0
                  ? `Live PaySim Transaction Ledger (${totalRows.toLocaleString()} Rows)`
                  : 'Live Cloud Transaction Stream (0 Hosted Rows)'}
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-blue-50 text-blue-700 border border-blue-200">
                {totalRows > 0 ? 'Continuous Stream' : 'Scanning Cloud'}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              Real-time payment ingestion routing through Anycast DNS into active cloud cluster
            </p>
          </div>
        </div>

        {/* Dynamic Route & Counter */}
        {isConnected ? (
          <div className="flex items-center space-x-3">
            <div className="text-right">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Live Dataset Count</div>
              <div className="text-sm font-black font-mono text-slate-900 tabular-nums">
                {(totalRows ?? 0).toLocaleString()}{' '}
                <span className="text-emerald-600 text-xs">
                  {totalRows > 0 ? '(Live Snowpipe)' : '(0 Ingested / Standby)'}
                </span>
              </div>
            </div>
            <div className="h-8 w-px bg-slate-200 hidden sm:block"></div>
            <span
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border flex items-center space-x-1.5 ${
                isAzure
                  ? 'bg-blue-50 text-blue-800 border-blue-200'
                  : 'bg-emerald-50 text-emerald-800 border-emerald-200'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isAzure ? 'bg-blue-500' : 'bg-emerald-500'} animate-ping`}></span>
              <span>Routing: {streamData?.active_route || activeCloud}</span>
            </span>
          </div>
        ) : (
          <span className="px-2.5 py-1 rounded-md text-[11px] font-mono text-slate-400 bg-slate-100 border border-slate-200">
            Status: Unlinked (--)
          </span>
        )}
      </div>

      {/* Stream Content */}
      <div className="mt-4">
        {!isConnected ? (
          <div className="p-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 text-center text-xs text-slate-500 font-medium">
            -- No active cloud connection. Connect accounts to stream live PaySim transactions across Primary and Secondary clouds --
          </div>
        ) : transactions.length === 0 ? (
          <div className="p-6 rounded-xl border border-dashed border-emerald-200 bg-emerald-50/40 text-center text-xs text-emerald-800 font-medium">
            -- 0 Application Datasets Hosted on Primary Cloud. Probe is scanning AWS S3, RDS, EC2, and Snowflake every 5s for live transactions. --
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-100">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-black text-slate-400 uppercase tracking-wider">
                  <th className="py-2 px-3">Time</th>
                  <th className="py-2 px-3">Transaction ID</th>
                  <th className="py-2 px-3">Type</th>
                  <th className="py-2 px-3 text-right">Amount</th>
                  <th className="py-2 px-3">Origin ➔ Destination</th>
                  <th className="py-2 px-3">Active Ingestion Route</th>
                  <th className="py-2 px-3">Latency</th>
                  <th className="py-2 px-3 text-center">Fraud Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-[11px]">
                {transactions.map((tx, idx) => (
                  <tr key={tx.tx_id || idx} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-2 px-3 text-slate-400">{tx.timestamp}</td>
                    <td className="py-2 px-3 font-bold text-slate-800">{tx.tx_id}</td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          tx.type === 'TRANSFER'
                            ? 'bg-purple-50 text-purple-700 border border-purple-200'
                            : tx.type === 'PAYMENT'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : tx.type === 'CASH_OUT'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {tx.type}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right font-black text-slate-900 tabular-nums">
                      ${tx.amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-2 px-3 text-slate-500">
                      {tx.nameOrig} ➔ {tx.nameDest}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold inline-flex items-center space-x-1 ${
                          isAzure ? 'text-blue-700 bg-blue-50' : 'text-emerald-700 bg-emerald-50'
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                        <span>{tx.route}</span>
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-500 tabular-nums">{tx.latency_ms}ms</td>
                    <td className="py-2 px-3 text-center">
                      {tx.isFraud ? (
                        <span className="inline-flex items-center space-x-1 text-red-600 font-bold text-[10px]">
                          <ShieldAlert className="w-3 h-3" />
                          <span>Flagged</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 text-emerald-600 text-[10px]">
                          <ShieldCheck className="w-3 h-3" />
                          <span>Pass</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

